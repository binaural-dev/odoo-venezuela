from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update(
            {
                "account_analytic_id": self.analytic_account_id.id,
            }
        )
        return res
