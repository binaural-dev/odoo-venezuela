from odoo import api, fields, models, _


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"
    _auto = False


    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_rate = fields.Float(
        help="Foreign Rate of the invoice",
        readonly=True,
    )
    foreign_total_billed = fields.Monetary(
        help="Foreign Total of the invoice",
        readonly=True,
        currency_field="foreign_currency_id",
    )

    _depends = {
        "account.move": ["foreign_rate", "foreign_total_billed"],
    }

    def _select(self):
        return super()._select() + ", move.foreign_rate as foreign_rate, move.foreign_total_billed as foreign_total_billed"

    
