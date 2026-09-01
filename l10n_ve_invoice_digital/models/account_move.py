from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

from ..services.tfhka_document_service import VES_CURRENCY_NAMES


class AccountMove(models.Model):
    _inherit = "account.move"

    is_digitalized = fields.Boolean(default=False, copy=False, tracking=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._apply_payment_driven_multi_currency()
        return moves

    def write(self, vals):
        """Prevent disabling multi_currency_invoice while it is locked by a USD payment."""
        skip_guard = self.env.context.get('tfhka_skip_multi_currency_guard')
        if not skip_guard and 'multi_currency_invoice' in vals and not vals.get('multi_currency_invoice'):
            for move in self:
                if move.show_payment_box and move._has_usd_reconciled_payment():
                    raise ValidationError(
                        _(
                            "Cannot disable multi-currency invoicing: a payment in USD is already "
                            "linked to this invoice."
                        )
                    )
        res = super().write(vals)
        if not skip_guard:
            self._apply_payment_driven_multi_currency()
        return res

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

        # O19: invoice_date_display es la fecha fiscal del documento; invoice_date
        # queda reservada al cálculo de la tasa de cambio (ver l10n_ve_accountant).
        last_invoice = self.env["account.move"].search(
            domain, order="invoice_date_display desc, name desc", limit=1
        )

        current_invoice_date = self.invoice_date_display or fields.Date.today()

        if last_invoice and last_invoice.invoice_date_display:
            if current_invoice_date < last_invoice.invoice_date_display:
                raise ValidationError(
                    _(
                        "The emission date of the current invoice is earlier than the date of "
                        "the last digitalized invoice (%(invoice_date)s). "
                        "This could cause sequence inconsistencies."
                    )
                    % {"invoice_date": last_invoice.invoice_date_display}
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

    # --- MULTI-MONEDA ---
    # Flag por factura: habilita el selector de moneda de línea.
    # Requiere que multi_currency_invoice_tfhka esté activo en la compañía.
    multi_currency_invoice = fields.Boolean(
        string='Multi-Currency Invoice',
        default=False,
        copy=False,
        tracking=True,
        help="When enabled, the 'Line Currency' selector appears, allowing you to choose "
             "between the base currency (VES) and the pricelist currency (USD/EUR). The "
             "document is then reported to TFHKA in both currencies. "
             "Requires 'Multi-currency digital invoicing' in company settings."
    )
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
    # ya hay un pago en divisa conciliado con la factura: en ese caso el
    # multi-moneda pasa a ser obligatorio (no se puede desmarcar).
    multi_currency_invoice_lock = fields.Boolean(
        compute='_compute_multi_currency_invoice_lock',
        string='Multi-Currency Invoice Lock',
    )

    @api.depends('show_payment_box', 'invoice_payments_widget')
    def _compute_multi_currency_invoice_lock(self):
        for move in self:
            is_locked = move.show_payment_box and move._has_usd_reconciled_payment()
            move.multi_currency_invoice_lock = is_locked
            if is_locked and not move.multi_currency_invoice:
                move.multi_currency_invoice = True
            elif not is_locked and move.multi_currency_invoice:
                pricelist_currency = move._get_pricelist_currency()
                pricelist_is_foreign = (
                    pricelist_currency and pricelist_currency != move.company_id.currency_id
                )
                if not pricelist_is_foreign:
                    move.multi_currency_invoice = False
                    move.line_currency_id = False

    def _apply_payment_driven_multi_currency(self):
        """Fuerza la multi-moneda cuando la dirige un pago en divisa conciliado.

        Vive en ``create``/``write`` y no dentro de un ``compute`` (como hacía
        17.0): escribir un campo almacenado como efecto lateral de un compute
        depende de cuándo se recalcule el campo técnico y deja el flag sin
        aplicar en escrituras que no lo disparan. Mismo patrón que
        ``binaural_unidigital._unidigital_apply_payment_driven_multicurrency``.
        """
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            if not (move.show_payment_box and move._has_usd_reconciled_payment()):
                continue
            vals = {}
            if not move.multi_currency_invoice:
                vals['multi_currency_invoice'] = True
            if not move.line_currency_id:
                pricelist_currency = move._get_pricelist_currency()
                if pricelist_currency and pricelist_currency != move.company_id.currency_id:
                    # Tarifa en divisa: usar la moneda de la tarifa.
                    vals['line_currency_id'] = pricelist_currency.id
                else:
                    # Tarifa en moneda base: usar la moneda del pago en divisa.
                    payment_currency = move._get_payment_driven_currency()
                    if payment_currency:
                        vals['line_currency_id'] = payment_currency.id
            if vals:
                move.with_context(tfhka_skip_multi_currency_guard=True).write(vals)

    def _has_usd_reconciled_payment(self):
        """Check if any payment reconciled with this invoice is in foreign currency.

        Se considera "divisa" cualquier moneda que no sea el bolívar, en lugar
        del literal 'USD' de 17.0, para que el bloqueo funcione también con
        EUR/COP. Se comprueba contra el bolívar y no contra
        ``company_id.foreign_currency_id`` porque el rol de moneda base y alterna
        puede estar invertido según la configuración de la compañía.
        Mismo criterio que ``binaural_unidigital._has_foreign_payment_local``.
        """
        self.ensure_one()
        content = (self.invoice_payments_widget or {}).get('content', [])
        if not content:
            return False
        payment_ids = [item.get('account_payment_id') for item in content if item.get('account_payment_id')]
        payments = self.env['account.payment'].browse(payment_ids).exists()
        return any(
            payment.currency_id.name not in VES_CURRENCY_NAMES for payment in payments
        )

    # ------------------------------------------------------------------
    # Moneda de línea derivada de la tarifa
    # ------------------------------------------------------------------

    def _get_pricelist_currency(self):
        """Divisa implícita en la tarifa de la factura, con respaldo heredado.

        ``account_invoice_pricelist`` fuerza ``currency_id`` a la moneda de la
        tarifa, así que la tarifa es la fuente de verdad de la divisa del
        documento. Para registros sin tarifa (o creados por API) se cae a la
        moneda extranjera de la compañía. La cadena es la misma que consume
        el servicio, para que la UI y el payload nunca discrepen.
        """
        self.ensure_one()
        pricelist_currency = (
            self.pricelist_id.currency_id if "pricelist_id" in self._fields else False
        )
        return pricelist_currency or self.company_id.foreign_currency_id

    def _get_payment_driven_currency(self):
        """Primera moneda extranjera entre los pagos en divisa conciliados.

        Se usa como moneda de línea cuando la factura no tiene tarifa en divisa
        pero se reconcilia un pago en moneda extranjera (modo pago-primero).
        Devuelve un recordset vacío si no hay ningún pago en divisa.
        """
        self.ensure_one()
        if not self.show_payment_box:
            return self.env["res.currency"]
        content = (self.invoice_payments_widget or {}).get("content", [])
        payment_ids = [
            item.get("account_payment_id")
            for item in content
            if item.get("account_payment_id")
        ]
        if not payment_ids:
            return self.env["res.currency"]
        payments = self.env["account.payment"].browse(payment_ids).exists()
        foreign = payments.filtered(
            lambda p: p.currency_id.name not in VES_CURRENCY_NAMES
        ).mapped("currency_id")
        return foreign[:1]

    multi_currency_available = fields.Boolean(
        string='Multi-currency available',
        compute='_compute_multi_currency_available',
        help="Técnico: True cuando la tarifa está en una moneda distinta a la "
             "moneda base de la compañía. Controla si el usuario puede marcar "
             "'Multi-Currency Invoice'.",
    )
    allowed_line_currency_ids = fields.Many2many(
        'res.currency',
        string='Allowed Line Currencies',
        compute='_compute_allowed_line_currency_ids',
        help="Técnico: monedas admitidas en 'Line Currency' — la moneda base "
             "(VES) y la moneda de la tarifa seleccionada.",
    )
    line_currency_id = fields.Many2one(
        'res.currency',
        string='Line Currency',
        copy=False,
        tracking=True,
        domain="[('id', 'in', allowed_line_currency_ids)]",
        help="Currency used for the product line prices sent to TFHKA. It can only "
             "be the company base currency (VES) or the pricelist currency; the "
             "document is totalled in both currencies from this selection.",
    )

    @api.depends('pricelist_id', 'pricelist_id.currency_id',
                 'company_id.currency_id', 'company_id.foreign_currency_id',
                 'show_payment_box', 'invoice_payments_widget')
    def _compute_multi_currency_available(self):
        for move in self:
            pricelist_currency = move._get_pricelist_currency()
            pricelist_foreign = bool(
                pricelist_currency and pricelist_currency != move.company_id.currency_id
            )
            payment_driven = (
                move.show_payment_box and move._has_usd_reconciled_payment()
            )
            move.multi_currency_available = pricelist_foreign or payment_driven

    @api.depends('pricelist_id', 'pricelist_id.currency_id',
                 'company_id.currency_id', 'company_id.foreign_currency_id',
                 'show_payment_box', 'invoice_payments_widget')
    def _compute_allowed_line_currency_ids(self):
        for move in self:
            currencies = move.company_id.currency_id | move._get_pricelist_currency()
            if move.show_payment_box and move._has_usd_reconciled_payment():
                payment_currency = move._get_payment_driven_currency()
                if payment_currency:
                    currencies |= payment_currency
            move.allowed_line_currency_ids = [(6, 0, currencies.ids)]

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id_tfhka(self):
        """La tarifa manda: al cambiarla se recalcula qué es válido."""
        for move in self:
            if not move.multi_currency_available:
                move.multi_currency_invoice = False
                move.line_currency_id = False
            elif (
                move.line_currency_id
                and move.line_currency_id not in move.allowed_line_currency_ids
            ):
                move.line_currency_id = False

    @api.onchange('multi_currency_invoice')
    def _onchange_multi_currency_invoice_tfhka(self):
        for move in self:
            if not move.multi_currency_invoice:
                move.line_currency_id = False
            elif not move.line_currency_id and move.multi_currency_available:
                move.line_currency_id = move._get_pricelist_currency()

    @api.constrains('multi_currency_invoice', 'line_currency_id', 'pricelist_id', 'move_type')
    def _check_multi_currency_consistency(self):
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            if not move.multi_currency_invoice:
                continue
            payment_driven = move.show_payment_box and move._has_usd_reconciled_payment()
            if not payment_driven and not move.multi_currency_available:
                raise ValidationError(
                    _(
                        "'Multi-Currency Invoice' cannot be enabled when the selected "
                        "pricelist is in the company base currency (%(currency)s)."
                    )
                    % {"currency": move.company_id.currency_id.name}
                )
            if (
                move.line_currency_id
                and move.line_currency_id not in move.allowed_line_currency_ids
            ):
                raise ValidationError(
                    _(
                        "'Line Currency' must be either the company base currency "
                        "(%(base)s) or the pricelist currency (%(pricelist)s)."
                    )
                    % {
                        "base": move.company_id.currency_id.name,
                        "pricelist": move._get_pricelist_currency().name or "-",
                    }
                )

    def copy_data(self, default=None):
        """Propaga la configuración multi-moneda a notas de crédito y débito.

        Tanto el asistente de reversión como el de nota de débito crean el
        documento vía ``copy``. Los campos son ``copy=False`` para no arrastrar
        valores obsoletos en un duplicado normal, así que hay que reinyectarlos
        aquí cuando la copia es realmente una NC/ND.
        """
        data_list = super().copy_data(default=default)
        default = default or {}
        if not (default.get("reversed_entry_id") or default.get("debit_origin_id")):
            return data_list

        for move, data in zip(self, data_list):
            data["multi_currency_invoice"] = move.multi_currency_invoice
            data["line_currency_id"] = move.line_currency_id.id
            if "pricelist_id" in move._fields:
                data.setdefault("pricelist_id", move.pricelist_id.id)
        return data_list

    # Resuelve si esta factura debe tratarse como multi-moneda.
    # Es el flag de la factura y solo el flag: el ajuste de compañía
    # (multi_currency_invoice_tfhka) únicamente muestra el campo, y la presencia
    # de una tasa (foreign_rate) no convierte el documento en bimoneda.
    def is_invoice_multi_currency_enabled(self):
        self.ensure_one()
        return bool(self.multi_currency_invoice)

    def generate_document_digital(self):
        # Toda la lógica vive en la capa de servicios (tfhka.document.service).
        return self.env["tfhka.document.service"].send_document(self)

    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'is_digitalized')
    def _compute_invisible_check(self):
        for record in self:
            record.show_digital_invoice = True
            record.show_digital_debit_note = True
            record.show_digital_credit_note = True

            if (
                record.state != "posted"
                or record.is_digitalized
                or not record.company_id.invoice_digital_tfhka
                or not record.journal_id.digital_invoice
            ):
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
