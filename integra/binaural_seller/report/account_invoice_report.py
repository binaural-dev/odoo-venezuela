from odoo import api, fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    seller_id = fields.Many2one(
        "hr.employee", string="Vendedores", help="Vendedor encargado de la venta"
    )

    @api.model
    def _select(self):
        res = super()._select()
        res += """,
            move.seller_id as seller_id
        """
        return res
