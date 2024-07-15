from odoo import api, fields, models


class SetCommissionOrderToInvoice(models.TransientModel):
    _inherit = "set.commission.order.to.invoice"

    pos_order_ids = fields.Many2many("pos.order")
    is_pos = fields.Boolean(compute="_compute_is_pos")

    @api.depends("pos_order_ids")
    def _compute_is_pos(self):
        for record in self:
            record.is_pos = len(record.pos_order_ids) > 0

    def get_orders(self):
        if self.pos_order_ids:
            return self.pos_order_ids.filtered(
                lambda x: x.state in ["paid", "posted", "invoiced"]
            )
        return super().get_orders()

    def get_order_lines(self):
        if self.pos_order_ids:
            return self.get_orders().lines
        return super().get_order_lines()

    def get_invoices(self):
        if self.pos_order_ids:
            return self.get_orders().account_move
        return super().get_invoices()
