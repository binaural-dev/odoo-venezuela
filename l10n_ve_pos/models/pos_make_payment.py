from odoo import _, models
from odoo.exceptions import UserError


class PosMakePayment(models.TransientModel):
    _inherit = "pos.make.payment"

    def check(self):
        self.ensure_one()
        order = self.env["pos.order"].browse(self.env.context.get("active_id", False))
        if self.payment_method_id.split_transactions and not order.partner_id:
            raise UserError(
                _(
                    "Customer is required for %s payment method.",
                    self.payment_method_id.name,
                )
            )
        return super().check()
