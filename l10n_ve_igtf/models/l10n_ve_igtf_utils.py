from odoo import api, fields, models
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import UserError


class IGTFUtils(models.AbstractModel):
    _name = "l10n_ve_igtf.utils"
    _description = "IGTF Shared Utilities"

    @api.model
    def calculate_igtf_for_payment(
        self, invoice, amount_payment, payment_currency,
        payment_date, company=None, base=False, indexed_default=True
    ):
        company = company or self.env.company
        currency = invoice.currency_id
        precision = currency.rounding
        date_conver = payment_date if indexed_default else invoice.invoice_date

        due_amount = self._convert_to_company_currency(
            invoice.currency_id, invoice.amount_residual, date_conver, company
        )
        payment_amount = self._convert_to_company_currency(
            payment_currency, amount_payment, date_conver, company
        )

        principal_amount = min(payment_amount, due_amount)
        igtf_unrounded = principal_amount * (company.igtf_percentage / 100)

        igtf_top = invoice.igtf_top_aply
        alter_bi_igtf = invoice.alter_bi_igtf
        igtf = igtf_unrounded
        invoice_residual = due_amount

        if not float_is_zero(igtf, precision_rounding=precision) and igtf_top == invoice_residual:
            return 0.0

        residual_igtf = igtf_top - alter_bi_igtf

        if float_compare(residual_igtf, 0.0, precision_rounding=precision) == 0.0:
            return 0.0

        if igtf > residual_igtf and not float_is_zero(residual_igtf, precision_rounding=precision):
            igtf = residual_igtf

        if float_compare(igtf_top, 0.0, precision_rounding=precision) >= 0.0 \
                and float_compare(igtf, igtf_top, precision_rounding=precision) > 0.0:
            return 0.0

        if not base:
            return self._convert_to_external_currency(payment_currency, igtf, date_conver, company)
        return igtf

    @api.model
    def _convert_to_company_currency(self, from_currency, amount, date, company, invoice_currency=None):
        company_currency = company.currency_id
        if from_currency == company_currency and invoice_currency == company_currency:
            return amount
        elif from_currency == company_currency and invoice_currency and invoice_currency != company_currency:
            return invoice_currency._convert(amount, company_currency, company, date or fields.Date.today())
        else:
            return from_currency._convert(amount, company_currency, company, date or fields.Date.today())

    @api.model
    def _convert_to_external_currency(self, from_currency, amount, date, company):
        company_currency = company.currency_id
        return company_currency._convert(amount, from_currency, company, date or fields.Date.today())

    @api.model
    def get_moves_from_context(self):

        ids=self.env.context.get("active_id") or self.env.context.get("active_ids")
        if isinstance(ids, int):
            return self.env["account.move"].browse([ids])
        else:
            move_lines = self.env["account.move.line"].browse(ids)
            return set(move_lines.mapped("move_id"))
