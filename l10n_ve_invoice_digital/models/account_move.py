import json
import re
from datetime import timedelta

from odoo import models, api, fields, tools, _
from odoo.exceptions import UserError, ValidationError

from ..services.tfhka_client import TFHKA_ENDPOINTS

# Safety cap so one cron run can't try to drain an unbounded backlog in a
# single transaction (risking hitting limit_time_cron on a long queue).
TFHKA_QUEUE_BATCH_SIZE = 200

# Safety margin absorbing clock drift between the Odoo app server (which
# stamps date_state via fields.Datetime.now()) and the database server
# (which stamps tfhka.api.log's create_date) when checking whether a log
# postdates a given attempt in _tfhka_reconcile_stuck_processing.
TFHKA_CLOCK_SKEW_MARGIN = timedelta(seconds=30)

# How long a document can sit in 'processing' with no matching success log
# before _tfhka_reconcile_stuck_processing gives up waiting and marks it
# 'error'. The cron runs every minute (ir_cron_tfhka_digitalization_queue),
# so in the common case a stuck document has already been sitting there for
# a full interval by the time the *next* run even looks at it -- this
# constant mirrors that same interval, it isn't an arbitrary number.
TFHKA_STUCK_PROCESSING_GRACE_PERIOD = timedelta(minutes=1)


class AccountMove(models.Model):
    _inherit = "account.move"

    is_digitalized = fields.Boolean(default=False, copy=False, tracking=True)

    # --- Encolado de digitalización TFHKA ---
    # Reemplaza la digitalización síncrona en el posteo (que hacía la llamada
    # HTTP a TFHKA inline desde move.action.post.alert.wizard.action_confirm(),
    # sin buena respuesta ante una llamada lenta/fallida más que bloquear al
    # usuario) por una cola: postear una factura solo la encola (una simple
    # escritura de campo); un cron avanza la cola un documento a la vez,
    # esperando cada respuesta antes de pasar al siguiente.
    #
    # Invariante que mantiene el cron (ver _tfhka_cron_process_queue): nunca
    # hay más de un documento en 'processing' ni más de uno en 'error' a la
    # vez. Un documento en 'error' detiene toda la cola hasta que un humano
    # lo resuelve (botón 'Retry Digitalization') -- la cola nunca salta un
    # fallo sin resolver, ya que el número de documento de TFHKA se calcula
    # como "último número de TFHKA + 1" al momento de enviar, y debe
    # mantenerse en estricto orden secuencial.
    tfhka_digitalization_state = fields.Selection(
        [
            ("none", "Not Digitalized"),
            ("queued", "Queued"),
            ("processing", "Processing"),
            ("success", "Digitalized"),
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
        help="When tfhka_digitalization_state last changed. Used by the cron "
             "to tell a healthy 'processing' attempt from one abandoned by an "
             "interrupted run (see TFHKA_STUCK_PROCESSING_GRACE_PERIOD).",
    )
    tfhka_digitalization_error = fields.Text(
        string="TFHKA Digitalization Error",
        copy=False,
        help="Error message from the last failed digitalization attempt. "
             "Cleared once the document digitalizes successfully.",
    )

    show_digital_invoice = fields.Boolean(compute="_compute_invisible_check", copy=False)
    show_digital_debit_note = fields.Boolean(string="Show Digital Note Debit", compute="_compute_invisible_check", copy=False)
    show_digital_credit_note = fields.Boolean(string="Show Digital Note Credit", compute="_compute_invisible_check", copy=False)

    show_payment_box = fields.Boolean(
        default=False,
        copy=False,
        tracking=True,
        help="If enabled, the digital invoice includes the payment methods block (formasPago).",
    )
    digitalization_with_payment_active = fields.Boolean(
        related="company_id.digitalization_with_payment_tfhka",
    )
    journal_digital_invoice = fields.Boolean(
        related="journal_id.digital_invoice",
        string="Journal Is Digital",
        help="Used to hide the TFHKA digitalization fields when the journal is not digital.",
    )

    def write(self, vals):
        """Prevent disabling multi_currency_invoice while it is locked by a USD payment.

        Also stamps date_state on every tfhka_digitalization_state change --
        the crash-recovery guard (_tfhka_reconcile_stuck_processing) reads it
        to tell how long a document has been in its current state."""
        if 'multi_currency_invoice' in vals and not vals.get('multi_currency_invoice'):
            for move in self:
                if move.show_payment_box and move._has_usd_reconciled_payment():
                    raise ValidationError(
                        _(
                            "Cannot disable multi-currency invoicing: a payment in USD is already "
                            "linked to this invoice."
                        )
                    )
        if 'tfhka_digitalization_state' in vals:
            vals = dict(vals, date_state=fields.Datetime.now())
        return super().write(vals)

    def action_post(self):
        for invoice in self:
            invoice._tfhka_validate_mixed_invoicing()
            invoice._tfhka_validate_invoice_date()

        # Marca de contexto: l10n_ve_payment_extension crea y postea las
        # retenciones de proveedor (IVA/ISLR) dentro de esta misma cadena de
        # super(); el contexto se propaga hasta account.retention.action_post()
        # para que sepa que la retención vino de la factura y pueda
        # auto-digitalizarse (ver account_retention.py).
        res = super(AccountMove, self.with_context(l10n_ve_invoice_digital_auto_retention=True)).action_post()
        return res

    def _tfhka_validate_invoice_date(self):
        """Validates that the emission date of the current invoice is not earlier than the date of the last digitalized invoice."""
        self.ensure_one()
        if not self._is_eligible_for_tfhka():
            return

        domain = [
            ("state", "=", "posted"),
            ("journal_id.digital_invoice", "=", True),
            ("journal_id", "=", self.journal_id.id),
            ("move_type", "=", self.move_type),
            ("is_digitalized", "=", True),
        ]

        last_invoice = self.env["account.move"].search(
            domain, order="invoice_date desc, name desc", limit=1
        )

        current_invoice_date = self.invoice_date or fields.Date.today()

        if last_invoice and last_invoice.invoice_date:
            if current_invoice_date < last_invoice.invoice_date:
                raise ValidationError(
                    _(
                        "The emission date of the current invoice is earlier than the date of the last digitalized invoice (%(invoice_date)s). "
                        "This could cause sequence inconsistencies.",
                        invoice_date=last_invoice.invoice_date,
                    )
                )

    def _is_eligible_for_tfhka(self):
        """Check if the invoice should process TFHKA logic."""
        self.ensure_one()
        config_invoice_can_be_digitalized = self.company_id.invoice_digital_tfhka
        if not self.journal_id.digital_invoice or not config_invoice_can_be_digitalized:
            return False
        if self.move_type not in ("out_invoice", "out_refund"):
            return False
        return True

    def _tfhka_validate_mixed_invoicing(self):
        """Validates if mixed invoicing is allowed."""
        self.ensure_one()
        config_invoice_can_be_digitalized = self.company_id.invoice_digital_tfhka
        config_mix_invoicing = self.company_id.mix_invoicing_tfhka

        if not self.journal_id.digital_invoice and config_invoice_can_be_digitalized and not config_mix_invoicing:
            if self.move_type in ['out_invoice', 'out_refund']:
                raise ValidationError(_(
                    "The company is configured for strict digital invoicing (mixed invoicing is disabled). "
                    "Only journals with digital invoicing enabled are allowed for this operation. "
                    "Please check the company configuration or select a valid digital journal."
                ))

    def _tfhka_get_document_type_and_series(self):
        """Returns the TFHKA document type and series."""
        self.ensure_one()
        document_type = ""
        if self.move_type == "out_invoice":
            document_type = "03" if self.debit_origin_id else "01"
        elif self.move_type == "out_refund" and self.reversed_entry_id:
            document_type = "02"
        
        series = ""
        if self.company_id.group_sales_invoicing_series and self.journal_id.series_correlative_sequence_id:
            if self.journal_id.sequence_id and self.journal_id.sequence_id.prefix:
                series = re.sub(r'[^a-zA-Z0-9]', '', self.journal_id.sequence_id.prefix)
            else:
                raise UserError(_("The selected series is not configured"))
                
        return document_type, series

    # --- MULTI-MONEDA ---
    # Flag por factura: habilita el selector de moneda de línea (VES/USD).
    # Requiere que multi_currency_invoice_tfhka esté activo en la compañía.
    multi_currency_invoice = fields.Boolean(
        string='Multi-Currency Invoice',
        compute='_compute_multi_currency_invoice',
        store=True,
        readonly=False,
        default=False,
        tracking=True,
        help="When enabled, the 'Line Currency' selector appears, allowing you to "
             "choose VES (prices in Bolivars, totals in VES) or USD (prices in USD, "
             "totals in both currencies). "
             "Requires 'Multi-currency digital invoicing' in company settings."
    )

    @api.depends('show_payment_box', 'invoice_payments_widget')
    def _compute_multi_currency_invoice(self):
        """Se autocompleta a True cuando el cuadro de pago está activo y hay un
        pago en USD conciliado: ahí el multimoneda es obligatorio.

        Campo computado almacenado con ``readonly=False`` (patrón de Odoo para
        "se sugiere solo, pero el usuario puede editarlo"): así la escritura la
        hace el motor de recompute y no un compute ajeno. Antes esto vivía
        dentro de ``_compute_multi_currency_invoice_lock``, que al estar su
        campo en la vista escribía en account.move cada vez que se abría la
        factura (AccessError para usuarios de solo lectura, escritura sobre
        asientos publicados y un mensaje de chatter por apertura).

        Fuera del caso obligatorio se conserva el valor persistido vía
        ``_origin``, para que el recompute no pise lo que eligió el usuario.
        """
        for move in self:
            if move.show_payment_box and move._has_usd_reconciled_payment():
                move.multi_currency_invoice = True
            else:
                move.multi_currency_invoice = move._origin.multi_currency_invoice or False
    # Indica si la funcionalidad multi-moneda está disponible (según compañía).
    # Controla la visibilidad del campo multi_currency_invoice en vista.
    multi_currency_enabled = fields.Boolean(
        string='Multi-currency enabled',
        compute='_compute_multi_currency_enabled',
        store=False
    )

    @api.depends('company_id.multi_currency_invoice_tfhka')
    def _compute_multi_currency_enabled(self):
        for move in self:
            move.multi_currency_enabled = move.company_id.multi_currency_invoice_tfhka

    # Bloquea multi_currency_invoice cuando el cuadro de pago está activo y
    # ya hay un pago en USD conciliado con la factura: en ese caso el
    # multi-moneda pasa a ser obligatorio (no se puede desmarcar).
    multi_currency_invoice_lock = fields.Boolean(
        compute='_compute_multi_currency_invoice_lock',
        string='Multi-Currency Invoice Lock',
    )

    @api.depends('show_payment_box', 'invoice_payments_widget')
    def _compute_multi_currency_invoice_lock(self):
        # Solo calcula el lock. La auto-activación de multi_currency_invoice
        # vive en su propio compute (ver _compute_multi_currency_invoice).
        for move in self:
            move.multi_currency_invoice_lock = (
                move.show_payment_box and move._has_usd_reconciled_payment()
            )

    def _has_usd_reconciled_payment(self):
        """Check if any payment reconciled with this invoice is in USD."""
        self.ensure_one()
        content = (self.invoice_payments_widget or {}).get('content', [])
        if not content:
            return False
        payment_ids = [item.get('account_payment_id') for item in content if item.get('account_payment_id')]
        payments = self.env['account.payment'].browse(payment_ids).exists()
        return any(payment.currency_id.name == 'USD' for payment in payments)

    # Moneda de las líneas de producto: VES (precios en Bs.) o USD (precios en USD).
    # Solo visible cuando multi_currency_invoice está activo en la factura.
    line_currency = fields.Selection([
        ('VES', 'VES'),
        ('USD', 'USD'),
    ], default='VES',
       help="VES: line prices in Bolivars, totals in VES only.\n"
            "USD: line prices in US dollars, totals in both currencies.")

    # Resuelve si esta factura debe tratarse como multi-moneda.
    # El modo multi-moneda (USD + totales bimoneda) se activa solo cuando
    # multi_currency_invoice=True y line_currency='USD'.
    # Sigue el patrón de binaural_unidigital con la adición de line_currency.
    def is_invoice_multi_currency_enabled(self):
        self.ensure_one()
        return bool(self.multi_currency_invoice and self.line_currency == 'USD')

    def generate_document_digital(self):
        # Toda la lógica vive en la capa de servicios (tfhka.document.service).
        return self.env["tfhka.document.service"].send_document(self)

    def action_tfhka_generate_digital(self):
        """Manual 'Generate Digital ...' button: enqueue only -- the actual
        TFHKA call always happens through the queue/cron, never inline in
        this request. In "digitalization with payment" mode this button is
        the ONLY entry point to the queue (see
        _tfhka_is_eligible_for_digitalization, always False in that mode),
        so it's the only place that can stop an unpaid or out-of-order
        invoice before it reaches 'queued'. Both validated BEFORE
        enqueueing so a failure here never touches
        tfhka_digitalization_state."""
        for move in self:
            move._tfhka_validate_previous_document_queued()
        self._check_tfhka_payment_required()
        self._tfhka_enqueue_digitalization()

    def _tfhka_validate_previous_document_queued(self):
        """Hard block: the previous posted document in this journal's own
        numbering (by name) must already be 'queued' or 'success' before
        this one can be sent to the queue. Only meaningful in
        "digitalization with payment" mode -- the only mode where a human
        chooses, via this button, which document to enqueue next; in
        normal mode documents are enqueued automatically at posting, in
        strict chronological order, so there's nothing retroactive to
        check. TFHKA requires strictly consecutive numbering, so letting a
        later document jump the queue ahead of an unsent earlier one would
        risk submitting them out of order.
        """
        self.ensure_one()
        previous = self.env["account.move"].search(
            [
                ("id", "!=", self.id),
                ("company_id", "=", self.company_id.id),
                ("journal_id", "=", self.journal_id.id),
                ("move_type", "=", self.move_type),
                ("state", "=", "posted"),
                ("name", "<", self.name),
            ],
            order="name desc",
            limit=1,
        )
        if previous and previous.tfhka_digitalization_state not in ("queued", "success"):
            raise ValidationError(
                _(
                    "Cannot queue %(name)s for digitalization: the previous document, "
                    "%(previous_name)s, is neither digitalized nor queued.",
                    name=self.name,
                    previous_name=previous.name,
                )
            )

    def _check_tfhka_payment_required(self):
        """In 'cash' mode, block digitalization until the invoice is paid.

        Same criteria as binaural_unidigital.AccountMove.
        _check_unidigital_payment_required: accepts ``paid``, ``in_payment``
        and ``reversed`` as satisfying the "paid" requirement, excludes
        credit notes (``out_refund``), and only applies in "digitalization
        with payment" mode (``digitalization_with_payment_tfhka``). All
        invoices are validated together and reported in a single error
        listing every offending invoice.
        """
        unpaid = self.filtered(
            lambda invoice: (
                invoice.move_type != "out_refund"
                and invoice.company_id.digitalization_with_payment_tfhka
                and invoice.company_id.payment_mode_tfhka == "cash"
                and invoice.payment_state not in ("paid", "in_payment", "reversed")
            )
        )
        if unpaid:
            raise ValidationError(
                _(
                    "The following invoices must have their payment in "
                    "process, be fully paid, or be reversed before they can "
                    "be digitalized:\n%s",
                    "\n".join(unpaid.mapped("name")),
                )
            )

    def _tfhka_is_eligible_for_digitalization(self):
        """True when this move should be queued for normal digitalization:
        digital journal, not already digitalized, and not in "digitalization
        with payment" mode (driven by the manual button instead -- see
        ``action_tfhka_generate_digital``)."""
        self.ensure_one()
        return (
            not self.is_digitalized
            and self.journal_id.digital_invoice
            and not self.company_id.digitalization_with_payment_tfhka
        )

    def _tfhka_enqueue_eligible_for_digitalization(self):
        """Enqueues each eligible move for TFHKA digitalization (queue
        processed by ``_tfhka_cron_process_queue``). Called from
        ``move.action.post.alert.wizard.action_confirm()`` right after
        posting."""
        eligible = self.filtered(lambda record: record._tfhka_is_eligible_for_digitalization())
        eligible._tfhka_enqueue_digitalization()

    def _tfhka_reconcile_success_from_log(self, log_entry):
        """See ``_tfhka_recover_stuck_processing`` below: replays
        ``tfhka.document.service._register_success`` using the
        response TFHKA already gave us for the interrupted attempt, instead
        of resubmitting. ``document_number`` is read back from the original
        *request* (not recomputed) because, in normal mode, it was TFHKA's
        own last-number-at-the-time plus one -- recomputing it now would give
        a different (wrong) number, since TFHKA's counter already moved past
        it once this document was accepted."""
        self.ensure_one()
        response = json.loads(log_entry.response_payload)
        request_payload = json.loads(log_entry.request_payload)
        document_number = (
            request_payload.get("documentoElectronico", {})
            .get("encabezado", {})
            .get("identificacionDocumento", {})
            .get("numeroDocumento")
        )
        self.env["tfhka.document.service"]._register_success(self, response, document_number)

    def _tfhka_commit(self):
        """Commits the current transaction -- except under the test runner,
        where Odoo's test framework forbids cr.commit()/rollback()."""
        if not tools.config["test_enable"]:
            self.env.cr.commit()  # pylint: disable=invalid-commit

    def _tfhka_enqueue_digitalization(self):
        """Enqueue: call this instead of generate_document_digital() directly.
        Never calls TFHKA -- just a field write, so it can't roll back the
        caller's transaction (e.g. the posting of the invoice itself)."""
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

        'queued' is the only valid entry state -- this is only ever called
        by the cron step, on a document it just fetched with that state;
        this is a defensive guard against any other caller triggering a real
        TFHKA call outside the queue on a document that isn't actually
        pending.
        """
        self.ensure_one()
        if self.tfhka_digitalization_state != "queued":
            return self.tfhka_digitalization_state == "success"
        self.write({"tfhka_digitalization_state": "processing"})
        # Committed right away -- durable proof that this specific attempt
        # started, so a kill during the TFHKA call below leaves the document
        # visibly 'processing' instead of silently rolling back to 'queued'.
        self._tfhka_commit()
        try:
            self.generate_document_digital()
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
                body=_("TFHKA digitalization failed: %s", error),
            )
            return False

    def _tfhka_recover_stuck_processing(self):
        """Called on every document found in 'processing' at the start of a
        cron tick. A healthy attempt is never observed here: one cron tick
        always resolves 'processing' to 'success'/'error' before it ends, so
        the only way a fresh tick can find one is a previous run that got
        interrupted mid-flight (Odoo killed, e.g. hitting limit_time_cron
        while waiting on TFHKA).

        Processed oldest-first (``date_state asc``) so that, if more than
        one document is stuck, an old one past the grace period gets
        resolved before a fresh one halts the loop.

        Returns True if it's safe to keep processing the queue this run
        (every stuck record was resolved, or there were none), False if at
        least one record is still within its grace period and was left
        untouched -- the caller must halt the queue for this run without
        even checking the error guard, so as not to advance past a document
        that may still be legitimately in flight.
        """
        stuck = self.search(
            [("tfhka_digitalization_state", "=", "processing")],
            order="date_state asc",
        )
        for record in stuck:
            resolved = record._tfhka_reconcile_stuck_processing()
            self._tfhka_commit()
            if not resolved:
                return False
        return True

    def _tfhka_reconcile_stuck_processing(self):
        """Returns True if this record was resolved (success or error),
        False if it's still within TFHKA_STUCK_PROCESSING_GRACE_PERIOD and
        was left untouched in 'processing'."""
        self.ensure_one()
        log_entry = self.env["tfhka.api.log"].sudo().search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("endpoint", "=", TFHKA_ENDPOINTS["emision"]),
                ("success", "=", True),
                ("create_date", ">=", self.date_state - TFHKA_CLOCK_SKEW_MARGIN),
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
                    "resubmitted.",
                    log_entry.id,
                ),
            )
            return True

        elapsed = fields.Datetime.now() - self.date_state
        if elapsed > TFHKA_STUCK_PROCESSING_GRACE_PERIOD:
            minutes = TFHKA_STUCK_PROCESSING_GRACE_PERIOD.seconds // 60
            self.write({
                "tfhka_digitalization_state": "error",
                "tfhka_digitalization_error": _(
                    "TFHKA digitalization was interrupted and no successful response "
                    "was found in the API log after waiting %(minutes)s minute(s). "
                    "There is no confirmation TFHKA received this document -- verify "
                    "with TFHKA before retrying manually, or a retry may submit a "
                    "duplicate.",
                    minutes=minutes,
                ),
            })
            self.message_post(
                body=_(
                    "TFHKA digitalization was interrupted before Odoo could record the "
                    "result, and no matching successful call was found in the API log "
                    "after waiting %(minutes)s minute(s). Marked as error instead of "
                    "being requeued automatically, since a blind retry risks submitting "
                    "a duplicate if TFHKA actually received the original request -- "
                    "verify directly with TFHKA before retrying.",
                    minutes=minutes,
                ),
            )
            return True

        return False

    def _tfhka_cron_process_queue(self):
        """Cron entry point -- operates on self (account.move).

        Queue lock: if there is already a document in 'error', nothing is
        processed -- that document must be resolved (retried successfully)
        before the rest of the queue can advance. Same halt applies, even
        earlier, if a document is still within its stuck-processing grace
        period (see _tfhka_recover_stuck_processing).
        """
        if not self._tfhka_recover_stuck_processing():
            return
        if self.search_count([("tfhka_digitalization_state", "=", "error")]):
            return
        queued = self.search(
            [("tfhka_digitalization_state", "=", "queued")],
            order="tfhka_queued_at asc, id asc",
            limit=TFHKA_QUEUE_BATCH_SIZE,
        )
        for record in queued:
            success = record._tfhka_process_digitalization()
            # Commit right after each document so its result is visible in
            # Odoo immediately, instead of only once the whole batch finishes.
            self._tfhka_commit()
            if not success:
                break  # halt the queue here; resumes once retried successfully

    def action_tfhka_retry_digitalization(self):
        """Button shown when state is 'error' (see the views). Only
        re-queues the document -- the cron (never this request) is what
        actually digitalizes it. Silently ignores any record not currently
        in 'error'.

        Deliberately does not go through _tfhka_enqueue_digitalization():
        that resets tfhka_queued_at to now, which would send the document
        to the back of the FIFO queue -- behind every document queued while
        it sat in 'error'. A retry must resume the queue at the same
        position it halted it."""
        eligible = self.filtered(lambda record: record.tfhka_digitalization_state == "error")
        eligible.write({
            "tfhka_digitalization_state": "queued",
            "tfhka_digitalization_error": False,
        })

    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'is_digitalized')
    def _compute_invisible_check(self):
        for record in self:
            record.show_digital_invoice = True
            record.show_digital_debit_note = True
            record.show_digital_credit_note = True

            if record.state != "posted" or record.is_digitalized or not record.company_id.invoice_digital_tfhka or not record.journal_id.digital_invoice:
                continue

            if (
                record.reversed_entry_id
                and record.reversed_entry_id.is_digitalized
            ):
                record.show_digital_credit_note = False

            elif (
                record.debit_origin_id
                and record.debit_origin_id.is_digitalized
            ):
                record.show_digital_debit_note = False

            elif (
                record.move_type == "out_invoice"
                and not record.debit_origin_id
            ):
                record.show_digital_invoice = False
