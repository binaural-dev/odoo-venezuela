from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=[("is_subsidiary", "=", True)],
    )

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update(
            {
                "account_analytic_id": self.subsidiary_id.id,
            }
        )
        return res
