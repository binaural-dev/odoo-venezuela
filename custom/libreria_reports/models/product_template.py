from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    lib_reordering_min_qty = fields.Float(
        compute="_compute_reordering_warehouse", compute_sudo=False
    )
    lib_reordering_max_qty = fields.Float(
        compute="_compute_reordering_warehouse", compute_sudo=False
    )

    def _compute_reordering_warehouse(self):
        for record in self:
            order_point = self.env["stock.warehouse.orderpoint"].search(
                [
                    ("product_tmpl_id", "=", record.id),
                    ("location_id", "=", record.env.company.store_location_id.id),
                ]
            )
            if not order_point:
                record.lib_reordering_min_qty = 0
                record.lib_reordering_max_qty = 0
                continue

            record.lib_reordering_min_qty = order_point.product_min_qty
            record.lib_reordering_max_qty = order_point.product_max_qty
