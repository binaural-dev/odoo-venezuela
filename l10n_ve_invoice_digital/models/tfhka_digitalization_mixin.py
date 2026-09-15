import logging
import time

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.tfhka_client import TFHKA_ENDPOINTS, _is_rate_limit_message

_logger = logging.getLogger(__name__)

# Wait applied when a single retry is attempted after TFHKA's rate-limit
# business error ("Consulta realizada previamente"). Short on purpose: this
# runs inside a cron transaction, not a web worker, so it can afford to wait
# without starving other requests -- but it's still a single attempt, not a
# loop, so a persistently rate-limited endpoint fails fast into 'error'
# instead of hammering TFHKA in a tight loop.
RATE_LIMIT_RETRY_WAIT = 5

# Safety cap so one cron run can't try to drain an unbounded backlog in a
# single transaction (risking hitting limit_time_cron on a long queue).
QUEUE_BATCH_SIZE = 200


class TfhkaDigitalizationMixin(models.AbstractModel):
    """Digitalization queue fields, shared by every TFHKA-digitalizable
    document (account.move, account.retention, stock.picking).

    Replaces synchronous digitalization-on-confirm (which could roll back
    the document's own posting if TFHKA rejected the call, and which had no
    good answer for TFHKA's rate-limit under high volume) with a queue:
    confirming/posting a document only enqueues it (a plain field write, no
    HTTP call, so it can never roll back the posting); a cron processes the
    queue for each model in FIFO order, one document at a time, waiting for
    each response before moving to the next. A failure halts that model's
    queue until someone fixes and retries the failed document -- the queue
    never skips ahead of an unresolved failure.
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
    tfhka_processing_started_at = fields.Datetime(
        string="TFHKA Processing Started At",
        copy=False,
        help="When the current/last digitalization attempt started. Committed "
             "to the database immediately (unlike the rest of this attempt's "
             "writes) so that if Odoo is killed while waiting on TFHKA's "
             "response, this document is durably left in 'processing' instead "
             "of silently rolling back to 'queued'. On the next cron run, "
             "this timestamp scopes the tfhka.api.log lookup used to check "
             "whether TFHKA actually processed that specific interrupted "
             "attempt before it's safe to retry.",
    )
    tfhka_digitalization_error = fields.Text(
        string="TFHKA Digitalization Error",
        copy=False,
        help="Error message from the last failed digitalization attempt. "
             "Cleared once the document digitalizes successfully.",
    )

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
        the cron loop stops there and the document is left in 'error' for a
        human to review and retry manually.
        """
        self.ensure_one()
        self.write({
            "tfhka_digitalization_state": "processing",
            "tfhka_processing_started_at": fields.Datetime.now(),
        })
        # Committed right away -- durable proof that this specific attempt
        # started, so a kill during the TFHKA call below leaves the document
        # visibly 'processing' instead of silently rolling back to 'queued'.
        # See _tfhka_recover_stuck_processing().
        self.env.cr.commit()
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
            self.write({
                "tfhka_digitalization_state": "error",
                "tfhka_digitalization_error": str(error),
            })
            self.message_post(
                body=_("TFHKA digitalization failed: %s") % error,
            )
            return False

    def _tfhka_recover_stuck_processing(self):
        """Cleans up documents left in 'processing' by an attempt that never
        reached its own final write (Odoo killed mid-flight, e.g. hitting
        limit_time_cron while waiting on TFHKA's response).

        A record can only be found here if a *previous* run was interrupted:
        this cron job never overlaps with itself (ir.cron's row lock), and
        within one run records are processed one at a time -- so there is
        never a moment where another execution is legitimately still working
        on a record already in 'processing' when a fresh run starts.

        For each one, checks tfhka.api.log (written on an isolated cursor,
        so it survived the crash even though this record's own write didn't)
        for a successful '/Emision' call logged after this specific attempt
        started. Found -> TFHKA actually processed it; replay the success
        bookkeeping from the logged response instead of resubmitting (which
        would risk a duplicate). Not found -> no evidence TFHKA ever saw it,
        safe to requeue for a normal retry.
        """
        stuck = self.search([("tfhka_digitalization_state", "=", "processing")])
        for record in stuck:
            record._tfhka_reconcile_stuck_processing()
            self.env.cr.commit()

    def _tfhka_reconcile_stuck_processing(self):
        self.ensure_one()
        log_entry = self.env["tfhka.api.log"].sudo().search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("endpoint", "=", TFHKA_ENDPOINTS["emision"]),
                ("success", "=", True),
                ("create_date", ">=", self.tfhka_processing_started_at),
            ],
            order="create_date desc",
            limit=1,
        )
        if log_entry:
            self._tfhka_reconcile_success_from_log(log_entry)
            self.write({
                "tfhka_digitalization_state": "success",
                "tfhka_digitalization_error": False,
                "is_digitalized": True,
            })
            self.message_post(
                body=_(
                    "TFHKA digitalization was interrupted before Odoo could record the "
                    "result, but the API log shows it actually succeeded (see The Factory "
                    "HKA API Log #%s). Recovered automatically -- the document was not "
                    "resubmitted."
                ) % log_entry.id,
            )
        else:
            _logger.info(
                "TFHKA: %s #%s was left in 'processing' by an interrupted attempt with no "
                "matching successful call in tfhka.api.log -- requeuing for a clean retry.",
                self._name, self.id,
            )
            self.write({
                "tfhka_digitalization_state": "queued",
                "tfhka_processing_started_at": False,
            })

    def _tfhka_reconcile_success_from_log(self, log_entry):
        """Replays the bookkeeping a normal successful digitalization would
        have done, using the response TFHKA already gave us (stored in
        ``log_entry``) instead of calling TFHKA again. Each concrete model
        (account.move, account.retention, stock.picking) must implement
        this, since each records success differently (different fields,
        and account.move additionally resyncs its own sequence)."""
        raise NotImplementedError(
            "%s must implement _tfhka_reconcile_success_from_log()" % self._name
        )

    def _tfhka_cron_process_queue(self):
        """Cron entry point -- operates on self (the concrete model the
        calling cron is bound to: account.move, account.retention or
        stock.picking).

        Queue lock: if this model already has a document in 'error', nothing
        is processed -- that document must be resolved (retried
        successfully) before the rest of this model's queue can advance.
        """
        self._tfhka_recover_stuck_processing()
        if self.search_count([("tfhka_digitalization_state", "=", "error")]):
            return
        queued = self.search(
            [("tfhka_digitalization_state", "=", "queued")],
            order="tfhka_queued_at asc, id asc",
            limit=QUEUE_BATCH_SIZE,
        )
        for record in queued:
            success = record._tfhka_process_digitalization()
            # Commit right after each document so its result is visible in
            # Odoo immediately, instead of only once the whole batch (up to
            # QUEUE_BATCH_SIZE documents) finishes processing.
            self.env.cr.commit()
            if not success:
                break  # halt this model's queue here; resumes once retried successfully

    def _tfhka_cron_process_queue_multi(self, model_names):
        """Entry point for the single unified cron: interleaves the given
        models round-robin (one document at a time -- model A's 1st, model
        B's 1st, model C's 1st, model A's 2nd, ...) instead of draining one
        model's entire batch before starting the next. Otherwise a large
        backlog in one model (e.g. account.move) would starve the others
        for the whole run, since they'd never get a turn until it finished.

        ``model_names`` may include models that don't exist in this registry
        or never inherited this mixin (e.g. stock.picking when the dispatch
        guide module isn't installed) -- those are silently skipped, so the
        same call works regardless of which optional modules are present.

        Each model still halts independently on its own first error, exactly
        like ``_tfhka_cron_process_queue``, it just does so without blocking
        the other models' turns in this same run.
        """
        models = []
        for model_name in model_names:
            if model_name not in self.env.registry:
                continue
            model = self.env[model_name]
            if not hasattr(model, "_tfhka_process_digitalization"):
                continue
            model._tfhka_recover_stuck_processing()
            models.append(model)

        halted = set()
        queues = {}
        for model in models:
            if model.search_count([("tfhka_digitalization_state", "=", "error")]):
                halted.add(model._name)
                continue
            queues[model._name] = model.search(
                [("tfhka_digitalization_state", "=", "queued")],
                order="tfhka_queued_at asc, id asc",
                limit=QUEUE_BATCH_SIZE,
            )

        max_len = max((len(queue) for queue in queues.values()), default=0)
        for index in range(max_len):
            for model in models:
                name = model._name
                if name in halted:
                    continue
                queue = queues.get(name)
                if not queue or index >= len(queue):
                    continue
                record = queue[index]
                success = record._tfhka_process_digitalization()
                self.env.cr.commit()
                if not success:
                    halted.add(name)  # halt only this model; others keep going

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
        """Button shown when state == 'error'. Retries this one document and,
        on success, resumes the rest of this model's queue right away."""
        for record in self:
            if record._tfhka_process_digitalization():
                record._tfhka_cron_process_queue()

    def action_tfhka_generate_digital(self):
        """Manual 'Generate Digital ...' button: enqueue only. The actual
        TFHKA call always happens through the queue/cron -- never inline in
        this request -- so this can't bypass the queue's safety guarantees
        (rate-limit pacing, halt-on-error) even if it's ever invoked on more
        than one record at once (e.g. a "digitalization with payment"
        invoice, for which this button is the only enqueue trigger)."""
        self._tfhka_enqueue_digitalization()
