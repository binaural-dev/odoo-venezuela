import re

from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_digitalized = fields.Boolean(default=False, copy=False, tracking=True)
    show_digital_invoice = fields.Boolean(compute="_compute_invisible_check", copy=False)
    show_digital_debit_note = fields.Boolean(string="Show Digital Note Debit", compute="_compute_invisible_check", copy=False)
    show_digital_credit_note = fields.Boolean(string="Show Digital Note Credit", compute="_compute_invisible_check", copy=False)

    def action_post(self):
        for invoice in self:
            invoice._tfhka_validate_mixed_invoicing()
            invoice._tfhka_validate_invoice_date()

        res = super(AccountMove, self).action_post()
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
        default=False,
        tracking=True,
        help="When enabled, the 'Line Currency' selector appears, allowing you to "
             "choose VES (prices in Bolivars, totals in VES) or USD (prices in USD, "
             "totals in both currencies). "
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

    # Moneda de las líneas de producto: VES (precios en Bs.) o USD (precios en USD).
    # Solo visible cuando multi_currency_invoice está activo en la factura.
    line_currency = fields.Selection([
        ('VES', 'VES'),
        ('USD', 'USD'),
    ], default='VES',
       help="VES: precios de líneas en Bolívares, totales solo en VES.\n"
            "USD: precios de líneas en dólares, totales en ambas monedas.")

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

    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'is_digitalized')
    def _compute_invisible_check(self):
        for record in self:
            record.show_digital_invoice = True
            record.show_digital_debit_note = True
            record.show_digital_credit_note = True

            if record.state != "posted" or record.is_digitalized or not self.company_id.invoice_digital_tfhka or not record.journal_id.digital_invoice:
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
