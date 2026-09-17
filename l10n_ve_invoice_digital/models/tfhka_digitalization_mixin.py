import logging
import time
from datetime import timedelta

from odoo import _, fields, models, tools
from odoo.exceptions import AccessError, UserError

from ..services.tfhka_client import _is_rate_limit_message

_logger = logging.getLogger(__name__)

# Wait applied when a single retry is attempted after TFHKA's rate-limit
# business error ("Consulta realizada previamente"). Short on purpose: this
# runs inside a cron transaction, not a web worker, so it can afford to wait
# without starving other requests -- but it's still a single attempt, not a
# loop, so a persistently rate-limited endpoint fails fast into 'error'
# instead of hammering TFHKA in a tight loop.
RATE_LIMIT_RETRY_WAIT = 5

# How long a document may sit in 'processing' before a cron tick considers
# it abandoned (Odoo killed mid-flight, e.g. hitting limit_time_cron while
# waiting on TFHKA's response) and marks it 'error' as a timeout. Measured
# against ``date_state`` -- the moment this specific attempt started.
PROCESSING_TIMEOUT = timedelta(minutes=1)

# tfhka.api.log.endpoint value for a failed attempt that never reached
# TFHKA at all (e.g. a payload validation error, like a tax group with no
# TFHKA mapping) -- see _tfhka_log_local_failure().
LOCAL_VALIDATION_ENDPOINT = "(local validation)"

# Safety cap on how many rounds _tfhka_cron_process_queue_multi will
# advance through in a single cron run, so an unbounded backlog can't risk
# hitting limit_time_cron.
QUEUE_BATCH_SIZE = 200


class TfhkaDigitalizationMixin(models.AbstractModel):
    """Digitalization queue fields, shared by every TFHKA-digitalizable
    document (account.move, account.retention, stock.picking).

    Replaces synchronous digitalization-on-confirm (which could roll back
    the document's own posting if TFHKA rejected the call, and which had no
    good answer for TFHKA's rate-limit under high volume) with a queue:
    confirming/posting a document only enqueues it (a plain field write, no
    HTTP call, so it can never roll back the posting); a cron advances the
    queue for each model one document at a time, waiting for each response
    before moving to the next.

    Invariant maintained by that cron (see ``_tfhka_cron_step``): a given
    model never has more than one document in 'processing' and never more
    than one in 'error' at the same time. A document in 'error' halts the
    whole queue until a human resolves it -- the queue never skips ahead of
    an unresolved failure. Digitalization is only ever triggered by that
    cron step (never inline by a button or a request), so nothing else can
    race it into moving a document to 'processing'.
    """

    _name = "tfhka.digitalization.mixin"
    _description = "TFHKA Digitalization Queue Fields"

    tfhka_digitalization_state = fields.Selection(
        [
            ("none", "Not Digitalized"),
            ("queued", "Queued"),
            ("processing", "Processing"),
            ("success", "TFHKA Digitalization Success"),
            ("error", "Error"),
        ],
        default="none",
        copy=False,
        tracking=True,
        string="TFHKA Digitalization Status",
    )
    tfhka_queued_at = fields.Datetime(
        string="TFHKA Queued At",
        copy=False,
        help="When this document entered the digitalization queue. Determines "
             "the order in which the cron digitalizes queued documents "
             "(oldest first).",
    )
    date_state = fields.Datetime(
        string="TFHKA Digitalization State Date",
        copy=False,
        help="When tfhka_digitalization_state last changed. Kept up to date "
             "automatically (see write()); used by the cron to tell a "
             "healthy 'processing' attempt from one abandoned by an "
             "interrupted run (see PROCESSING_TIMEOUT).",
    )
    tfhka_digitalization_error = fields.Text(
        string="TFHKA Digitalization Error",
        copy=False,
        help="Error message from the last failed digitalization attempt. "
             "Cleared once the document digitalizes successfully.",
    )

    def write(self, vals):
        if "tfhka_digitalization_state" in vals:
            vals = dict(vals, date_state=fields.Datetime.now())
        return super().write(vals)

    def _tfhka_commit(self):
        """Commits the current transaction -- except under the test runner,
        where Odoo's test framework forbids cr.commit()/rollback() (it needs
        the whole test to stay inside one rollback-able savepoint). All the
        durability guarantees this mixin relies on (durable 'processing'
        marker, per-document visibility, crash recovery) only matter in real
        cron/request execution; skipping the commit in tests is safe since
        the test's own transaction rollback at teardown covers cleanup."""
        if not tools.config["test_enable"]:
            self.env.cr.commit()

    def _tfhka_enqueue_digitalization(self):
        """Enqueue: call this instead of generate_document_digital() directly
        from action_post()/button_validate(). Never calls TFHKA -- just a
        field write, so it can't roll back the caller's transaction."""
        for record in self:
            if record.tfhka_digitalization_state in ("queued", "processing"):
                continue
            record.write({
                "tfhka_digitalization_state": "queued",
                "tfhka_queued_at": fields.Datetime.now(),
                "tfhka_digitalization_error": False,
            })

    def _tfhka_process_digitalization(self):
        """Digitalize this single document. Returns True/False (success/failure).

        Retries once, waiting RATE_LIMIT_RETRY_WAIT seconds, specifically
        when the failure is TFHKA's rate-limit business error. Any other
        failure (or the retry's own failure) is not retried further here --
        the queue halts there and the document is left in 'error' for a
        human to review and retry manually.

        'queued' is the only valid entry state -- this is only ever called
        by the cron step, on a document it just fetched with that state, so
        this is a defensive guard, not the normal path: it protects against
        any other caller (present or future) triggering a real TFHKA call
        outside the queue on a document that isn't actually pending (e.g.
        one already 'success' or 'processing'), which would either
        re-submit an already-successful document as a duplicate, or race
        an attempt already in flight.
        """
        self.ensure_one()
        if self.tfhka_digitalization_state != "queued":
            _logger.warning(
                "TFHKA: refusing to digitalize %s #%s -- state is %r, not "
                "'queued'.",
                self._name, self.id, self.tfhka_digitalization_state,
            )
            return self.tfhka_digitalization_state == "success"
        self.write({"tfhka_digitalization_state": "processing"})
        # Committed right away -- durable proof that this specific attempt
        # started, so a kill during the TFHKA call below leaves the document
        # visibly 'processing' (with date_state marking when) instead of
        # silently rolling back to 'queued'. See _tfhka_cron_step().
        self._tfhka_commit()
        api_log = self.env["tfhka.api.log"].sudo()
        log_domain = [("res_model", "=", self._name), ("res_id", "=", self.id)]
        logged_before = api_log.search_count(log_domain)
        try:
            try:
                self.generate_document_digital()
            except UserError as error:
                if _is_rate_limit_message(str(error)):
                    _logger.warning(
                        "TFHKA rate limit digitalizing %s #%s, retrying once in %ss",
                        self._name, self.id, RATE_LIMIT_RETRY_WAIT,
                    )
                    time.sleep(RATE_LIMIT_RETRY_WAIT)
                    self.generate_document_digital()
                else:
                    raise
            self.write({
                "tfhka_digitalization_state": "success",
                "tfhka_digitalization_error": False,
                "is_digitalized": True,
            })
            return True
        except Exception as error:
            # Every real HTTP call already logged itself in tfhka.api.log
            # (see tfhka.api.client._log_call) before raising -- this only
            # fires for a failure that never got that far (e.g. a payload
            # validation error like a tax group with no TFHKA mapping),
            # which would otherwise be visible only in this document's
            # chatter and invisible in the query history a human actually
            # checks first when investigating TFHKA issues.
            if api_log.search_count(log_domain) <= logged_before:
                api_log.create({
                    "company_id": self.company_id.id,
                    "endpoint": LOCAL_VALIDATION_ENDPOINT,
                    "res_model": self._name,
                    "res_id": self.id,
                    "res_name": self.display_name,
                    "success": False,
                    "response_payload": str(error),
                })
            self.write({
                "tfhka_digitalization_state": "error",
                "tfhka_digitalization_error": str(error),
            })
            self.message_post(
                body=_("TFHKA digitalization failed: %s") % error,
            )
            return False

    def _tfhka_timeout_if_stuck(self):
        """Called on a single document found in 'processing' at the start
        of a cron tick (see _tfhka_cron_step). A healthy attempt is never
        observed here: one cron tick always resolves 'processing' to
        'success'/'error' before it ends, so the only way a fresh tick can
        find one is a previous run that got interrupted mid-flight (Odoo
        killed, e.g. hitting limit_time_cron while waiting on TFHKA).

        Marks it 'error' once it's been stuck for at least
        PROCESSING_TIMEOUT (per ``date_state``, the moment it entered
        'processing'), so a human notices via the alert banner and retry
        button instead of the queue staying silently blocked forever. Below
        that threshold, does nothing -- it's simply too soon to tell apart
        from a still-in-flight call.
        """
        self.ensure_one()
        if fields.Datetime.now() - self.date_state < PROCESSING_TIMEOUT:
            return
        message = _(
            "TFHKA digitalization timed out: this document was left in "
            "'Processing' for over %(minutes)s minute(s) without a "
            "response, and was marked as an error."
        ) % {"minutes": int(PROCESSING_TIMEOUT.total_seconds() // 60)}
        self.write({
            "tfhka_digitalization_state": "error",
            "tfhka_digitalization_error": message,
        })
        self.message_post(body=message)

    def _tfhka_cron_step(self):
        """Advances this model's queue by exactly one document, in this
        priority order:

        1. A document in 'error' halts everything: returns False, nothing
           else runs until a human resolves it (see
           action_tfhka_retry_digitalization).
        2. Otherwise, a document in 'processing' halts this step too (see
           _tfhka_timeout_if_stuck for why, and what happens to it) --
           returns False.
        3. Otherwise, the single oldest 'queued' document is digitalized.

        Returns True when a document was actually digitalized (whether it
        ended in 'success' or 'error') so the caller knows there may be
        more work to do; False when nothing happened this call (queue
        empty, or halted by 1./2. above) -- the caller's signal to stop.
        """
        if self.search_count([("tfhka_digitalization_state", "=", "error")]):
            return False
        stuck = self.search([("tfhka_digitalization_state", "=", "processing")], limit=1)
        if stuck:
            stuck._tfhka_timeout_if_stuck()
            return False
        record = self.search(
            [("tfhka_digitalization_state", "=", "queued")],
            order="tfhka_queued_at asc, id asc",
            limit=1,
        )
        if not record:
            return False
        record._tfhka_process_digitalization()
        return True

    def _tfhka_cron_process_queue_multi(self, model_names):
        """Entry point for the single unified cron: drains every model's
        queue, interleaved one document at a time (model A's 1st, model
        B's 1st, model C's 1st, model A's 2nd, ...) instead of draining
        one model's entire backlog before starting the next -- otherwise
        a large backlog in one model (e.g. account.move) would starve the
        others for this whole run, since they'd never get a turn until it
        finished. A model drops out of the rotation once its own
        _tfhka_cron_step() reports nothing more to do; the run ends once
        every model has dropped out, or after QUEUE_BATCH_SIZE rounds.

        ``model_names`` may include models that don't exist in this
        registry or never inherited this mixin (e.g. stock.picking when the
        dispatch guide module isn't installed) -- those are silently
        skipped, so the same call works regardless of which optional
        modules are present.
        """
        active = []
        for model_name in model_names:
            if model_name not in self.env.registry:
                continue
            model = self.env[model_name]
            if not hasattr(model, "_tfhka_process_digitalization"):
                continue
            active.append(model)

        for _ in range(QUEUE_BATCH_SIZE):
            if not active:
                break
            still_active = []
            for model in active:
                advanced = model._tfhka_cron_step()
                self._tfhka_commit()
                if advanced:
                    still_active.append(model)
            active = still_active

    def _tfhka_digitalization_alert_data(self, model_names):
        """Records currently blocking their model's queue (state == 'error'),
        across the given models, for the top-of-page alert banner (see
        ``views/tfhka_digitalization_alert.xml``).

        Internal-users only, and no ``sudo()``: the banner renders on every
        page (it's injected into ``web.layout``), including portal/public
        pages, so this must never run a real search for a non-internal
        visitor, and must only ever return records the current user could
        already open on their own -- respecting normal access rights and
        record rules, scoped to the companies actually allowed in this
        session (``self.env.companies``), not a client-supplied cookie.
        """
        if not self.env.user._is_internal():
            return []

        alerts = []
        for model_name in model_names:
            if model_name not in self.env.registry:
                continue
            model = self.env[model_name]
            if not hasattr(model, "_tfhka_process_digitalization"):
                continue
            try:
                records = model.search([
                    ("tfhka_digitalization_state", "=", "error"),
                    ("company_id", "in", self.env.companies.ids),
                ])
            except AccessError:
                continue
            for record in records:
                alerts.append({
                    "name": record.display_name,
                    "url": "/mail/view?model=%s&res_id=%s" % (model_name, record.id),
                })
        return alerts

    def action_tfhka_retry_digitalization(self):
        """Button shown when state == 'error'. Only re-queues the document
        -- the cron (never this request) is what actually digitalizes it,
        so a double-click before the view refreshes the button's
        visibility, or two sessions retrying the same document, can never
        race the cron into moving the same document to 'processing' twice.
        Silently ignores any record not currently in 'error'.

        Deliberately does not go through _tfhka_enqueue_digitalization():
        that resets tfhka_queued_at to now, which would send the document
        to the back of the FIFO queue -- behind every document queued
        while it sat in 'error'. A retry must resume the queue at the
        same position it halted it, so tfhka_queued_at is left untouched
        (e.g. document #5 of 10 fails and gets retried: it must be
        processed next, not after #6-#10)."""
        eligible = self.filtered(lambda record: record.tfhka_digitalization_state == "error")
        eligible.write({
            "tfhka_digitalization_state": "queued",
            "tfhka_digitalization_error": False,
        })

    def action_tfhka_generate_digital(self):
        """Manual 'Generate Digital ...' button: enqueue only. The actual
        TFHKA call always happens through the queue/cron -- never inline in
        this request -- so this can't bypass the queue's safety guarantees
        (rate-limit pacing, halt-on-error) even if it's ever invoked on more
        than one record at once (e.g. a "digitalization with payment"
        invoice, for which this button is the only enqueue trigger)."""
        self._tfhka_enqueue_digitalization()
