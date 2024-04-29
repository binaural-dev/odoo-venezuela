from odoo import fields, models, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _compute_warehouse_id(self):
        main_warehouse_id = self[0].env.company.main_warehouse_id
        user_warehouse_id = self[0].env.user.property_warehouse_id
        if not main_warehouse_id and not user_warehouse_id:
            return super()._compute_warehouse_id()
        for order in self:
            if order.state in ["draft", "sent"] or not order.ids:
                order.warehouse_id = (
                    main_warehouse_id
                    if main_warehouse_id and not user_warehouse_id
                    else user_warehouse_id
                )