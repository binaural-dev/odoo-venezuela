from odoo import fields, models, _, api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        if self._context.get("bypass_warehouse_subsidiary",False):
            return super().action_confirm()
        for order in self:
            if order.subsidiary_id.id != order.warehouse_id.subsidiary_id.id and order.company_subsidiary:
                raise ValidationError(_("The budget subsidiary must be the same Warehouse subsidiary."))
        return super().action_confirm()

    @api.onchange('subsidiary_id')
    def _onchange_subsidiary_id(self):
        if self.order_line:
            raise ValidationError(_("You cannot change the location because order lines already exist."))

        if self.subsidiary_id:
            warehouse = (
                self.env["stock.warehouse"]
                .sudo()
                .search(
                    [
                        ("subsidiary_id", "=", self.subsidiary_id.id),
                    ],
                    limit=1,
                )
            )
            self.warehouse_id = warehouse
