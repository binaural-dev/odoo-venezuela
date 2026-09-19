import logging
import time
from datetime import timedelta

from odoo import _, fields, models, tools
from odoo.exceptions import AccessError, UserError

from ..services.tfhka_client import TFHKA_ENDPOINTS, _is_rate_limit_message
from ..services.tfhka_service_base import TfhkaDataError

_logger = logging.getLogger(__name__)

# Wait applied when a single retry is attempted after TFHKA's rate-limit
# business error ("Consulta realizada previamente"). Short on purpose: this
# runs inside a cron transaction, not a web worker, so it can afford to wait
# without starving other requests -- but it's still a single attempt, not a
# loop, so a persistently rate-limited endpoint fails fast into 'error'
# instead of hammering TFHKA in a tight loop.
RATE_LIMIT_RETRY_WAIT = 5

# TFHKA business codes that mean "problem with this document's own data"
# (missing/malformed field, doesn't meet minimum validations) rather than a
# grave system/integration failure. See the digital printer's error code
# table: 203 = rejected for missing/malformed required field, 205 = doesn't
# meet minimum validations (art. 28). Any other code (or no code at all, e.g.
# a network/auth failure with no TFHKA business code) stays 'error' unless it
# is a TfhkaDataError -- see _tfhka_process_digitalization.
DATA_ERROR_TFHKA_CODES = {"203", "205"}

# Safety cap so one cron run can't try to drain an unbounded backlog in a
# single transaction (risking hitting limit_time_cron on a long queue).
QUEUE_BATCH_SIZE = 200

# Safety margin absorbing clock drift between the Odoo app server (which
# stamps tfhka_processing_started_at via fields.Datetime.now()) and the
# database server (which stamps tfhka.api.log's create_date) when checking
# whether a log postdates a given attempt in _tfhka_reconcile_stuck_processing.
# Measured up to ~2s between these two containers in this environment (and
# it's the kind of gap that can vary run to run, not a fixed constant) --
# 30s is deliberately far more generous than that. Safe to be generous: the
# closest "wrong" candidate this could accidentally match is a *previous*
# attempt's own log, and consecutive attempts on the same document are
# always at least RATE_LIMIT_RETRY_WAIT apart (automatic retry) or minutes
# apart (a human clicking retry), so even 30s of margin can't reach into
# genuinely unrelated territory.
CLOCK_SKEW_MARGIN = timedelta(seconds=30)

# How long a document can sit in 'processing' with no matching success log
# before _tfhka_reconcile_stuck_processing gives up waiting and marks it
# 'error'. The unified cron runs every minute (ir_cron_tfhka_digitalization_
# queue), so in the common case a stuck document has already been sitting
# there for a full interval by the time the *next* run even looks at it --
# this constant mirrors that same interval, it isn't an arbitrary number.
# Below this threshold, "no log yet" is indistinguishable from "TFHKA just
# hasn't answered/logged yet" (network latency, or the scheduler firing a
# hair early), so the record is left untouched in 'processing' and this
# model's queue halts for the rest of this run instead of risking a
# duplicate resubmission or wrongly erroring out a call that may still be
# in flight.
STUCK_PROCESSING_GRACE_PERIOD = timedelta(minutes=1)


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

    Invariant maintained by that cron (see ``_tfhka_cron_process_queue``): a given
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
            ("success", "Digitalized"),
            ("error", "Error"),
            ("data_error", "Data Error"),
            # Only ever written by account.move (see
            # _tfhka_should_mark_not_applicable) -- account.retention and
            # stock.picking have their own, different non-eligibility
            # criteria and never reach this value, even though it's part of
            # this shared Selection like every other value here.
            ("not_applicable", "Not Applicable"),
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
             "interrupted run (see STUCK_PROCESSING_GRACE_PERIOD).",
    )
    tfhka_digitalization_error = fields.Text(
        string="TFHKA Digitalization Error",
        copy=False,
        help="Error message from the last failed digitalization attempt. "
             "Cleared once the document digitalizes successfully.",
    )

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
        # visibly 'processing' instead of silently rolling back to 'queued'.
        # See _tfhka_recover_stuck_processing().
        self._tfhka_commit()
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
            # getattr is safe for any exception that can land here (network
            # errors, ValidationError from an empty token, plain UserError
            # for HTTP 401/non-200, TfhkaBusinessError for a TFHKA business
            # code) -- anything without a .tfhka_code (or with a code other
            # than 203/205) falls back to the grave 'error' state, unless it's
            # a TfhkaDataError: a local (our side) pre-flight check caught a
            # missing/invalid document field before ever calling TFHKA -- the
            # same kind of problem TFHKA itself would report as 203/205 had
            # it been sent, so it's classified the same way.
            tfhka_code = getattr(error, "tfhka_code", None)
            is_data_error = tfhka_code in DATA_ERROR_TFHKA_CODES or isinstance(error, TfhkaDataError)
            new_state = "data_error" if is_data_error else "error"
            self.write({
                "tfhka_digitalization_state": new_state,
                "tfhka_digitalization_error": str(error),
            })
            self.message_post(
                body=_("TFHKA digitalization failed: %s") % error,
            )
            return False

    def _tfhka_recover_stuck_processing(self):
        """Called on a single document found in 'processing' at the start
        of a cron tick (see _tfhka_cron_process_queue). A healthy attempt is never
        observed here: one cron tick always resolves 'processing' to
        'success'/'error' before it ends, so the only way a fresh tick can
        find one is a previous run that got interrupted mid-flight (Odoo
        killed, e.g. hitting limit_time_cron while waiting on TFHKA).

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
        would risk a duplicate). Not found -> falls to
        _tfhka_reconcile_stuck_processing's own time-based decision (error
        once STUCK_PROCESSING_GRACE_PERIOD has passed, otherwise left as-is).

        Processed oldest-first (``tfhka_processing_started_at asc``) so that,
        if more than one document of this model is stuck, an old one that's
        past the grace period gets resolved before a fresh one halts the
        loop -- order matters here, not just cosmetics.

        Returns True if it's safe to keep processing this model's queue this
        run (every stuck record was resolved, or there were none), False if
        at least one record is still within its grace period and was left
        untouched -- the caller must halt this model's queue for this run
        without even checking the error/data_error guard, so as not to
        advance past a document that may still be legitimately in flight.
        """
        stuck = self.search(
            [("tfhka_digitalization_state", "=", "processing")],
            order="tfhka_processing_started_at asc",
        )
        for record in stuck:
            resolved = record._tfhka_reconcile_stuck_processing()
            self._tfhka_commit()
            if not resolved:
                return False
        return True

    def _tfhka_reconcile_stuck_processing(self):
        """Returns True if this record was resolved (success or error),
        False if it's still within STUCK_PROCESSING_GRACE_PERIOD and was
        left untouched in 'processing'."""
        self.ensure_one()
        log_entry = self.env["tfhka.api.log"].sudo().search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("endpoint", "=", TFHKA_ENDPOINTS["emision"]),
                ("success", "=", True),
                ("create_date", ">=", self.tfhka_processing_started_at - CLOCK_SKEW_MARGIN),
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
            return True

        elapsed = fields.Datetime.now() - self.tfhka_processing_started_at
        if elapsed > STUCK_PROCESSING_GRACE_PERIOD:
            minutes = STUCK_PROCESSING_GRACE_PERIOD.seconds // 60
            self.write({
                "tfhka_digitalization_state": "error",
                "tfhka_digitalization_error": _(
                    "TFHKA digitalization was interrupted and no successful response "
                    "was found in the API log after waiting %(minutes)s minute(s). "
                    "There is no confirmation TFHKA received this document -- verify "
                    "with TFHKA before retrying manually, or a retry may submit a "
                    "duplicate."
                ) % {"minutes": minutes},
            })
            self.message_post(
                body=_(
                    "TFHKA digitalization was interrupted before Odoo could record the "
                    "result, and no matching successful call was found in the API log "
                    "after waiting %(minutes)s minute(s). Marked as error instead of "
                    "being requeued automatically, since a blind retry risks submitting "
                    "a duplicate if TFHKA actually received the original request -- "
                    "verify directly with TFHKA before retrying."
                ) % {"minutes": minutes},
            )
            return True

        _logger.info(
            "TFHKA: %s #%s has been in 'processing' for %s, still within the %s grace "
            "period -- leaving untouched and halting this model's queue for this cron run.",
            self._name, self.id, elapsed, STUCK_PROCESSING_GRACE_PERIOD,
        )
        return False

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

        Queue lock: if this model already has a document in 'error' or
        'data_error', nothing is processed -- that document must be resolved
        (retried successfully) before the rest of this model's queue can
        advance. Same halt applies, even earlier, if a document is still
        within its stuck-processing grace period (see
        _tfhka_recover_stuck_processing) -- it may still be legitimately in
        flight, so nothing else for this model is touched this run either.
        """
        if not self._tfhka_recover_stuck_processing():
            return
        if self.search_count([("tfhka_digitalization_state", "in", ("error", "data_error"))]):
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
            self._tfhka_commit()
            if not success:
                break  # halt this model's queue here; resumes once retried successfully

    def _tfhka_cron_process_queue_multi(self, model_names):
        """Entry point for the single unified cron: drains every model's
        queue, interleaved one document at a time (model A's 1st, model
        B's 1st, model C's 1st, model A's 2nd, ...) instead of draining
        one model's entire backlog before starting the next -- otherwise
        a large backlog in one model (e.g. account.move) would starve the
        others for this whole run, since they'd never get a turn until it
        finished. A model drops out of the rotation once its own queue is
        empty or halts on an error; the run ends once every model has
        dropped out, or after QUEUE_BATCH_SIZE rounds.

        ``model_names`` may include models that don't exist in this registry
        or never inherited this mixin (e.g. stock.picking when the dispatch
        guide module isn't installed) -- those are silently skipped, so the
        same call works regardless of which optional modules are present.

        Each model still halts independently on its own first error, exactly
        like ``_tfhka_cron_process_queue``, it just does so without blocking
        the other models' turns in this same run. Same isolation applies to
        a model whose stuck-processing recovery leaves a document untouched
        within its grace period (see ``_tfhka_recover_stuck_processing``) --
        only that model is added to ``halted``.
        """
        models = []
        halted = set()
        for model_name in model_names:
            if model_name not in self.env.registry:
                continue
            model = self.env[model_name]
            if not hasattr(model, "_tfhka_process_digitalization"):
                continue
            if not model._tfhka_recover_stuck_processing():
                halted.add(model._name)
            models.append(model)

        queues = {}
        for model in models:
            if model._name in halted:
                continue
            if model.search_count([("tfhka_digitalization_state", "in", ("error", "data_error"))]):
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
                self._tfhka_commit()
                if not success:
                    halted.add(name)  # halt only this model; others keep going

    def _tfhka_digitalization_alert_data(self, model_names):
        """Records currently blocking their model's queue (state in ('error',
        'data_error')), across the given models, for the top-of-page alert
        banner (see ``views/tfhka_digitalization_alert.xml``).

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
                    ("tfhka_digitalization_state", "in", ("error", "data_error")),
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
