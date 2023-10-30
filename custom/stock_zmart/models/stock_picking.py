from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def print_operation_albaran(self):
        return self.env.ref("stock_zmart.action_print_picking_order").report_action(self)

    shipping_weight = fields.Float(store=True, readonly=False)
    weight = fields.Float(store=True, readonly=False)
    warehouse_operator_id = fields.Many2one("stock.warehouse.operator")
    guide_sequence_id = fields.Many2one(
        'ir.sequence',
        default=lambda self: self.env.ref("stock_zmart.sequence_guide_number").id
    )
    guide = fields.Char(copy=False)
    origin_sale_id = fields.Many2one("sale.order", compute="_compute_origin_sale_id")

    @api.depends("origin")
    def _compute_origin_sale_id(self):
        for record in self:
            if record.origin:
                sale_id = self.env["sale.order"].sudo().search([("name", "=", record.origin)])
                if not sale_id:
                    record.origin_sale_id = False
                    continue
                record.origin_sale_id = sale_id

    def button_validate(self):

        super().button_validate()

        if not self.guide:
            if self.shipping_type == 'shipment' and self.sequence_code == 'PACK':
                guide_sequence = self.guide_sequence_id._next()
                self.update({'guide': guide_sequence})

    def write(self, vals):
        res = super().write(vals)
        if vals.get("shipping_weight", False):
            picking_ids = self.env["stock.picking"].search(
                [
                    "&",
                    ("origin", "=", self[0].origin),
                    ("shipping_weight", "!=", vals.get("shipping_weight")),
                ],
                limit=1,
            )
            if picking_ids:
                picking_ids.write({"shipping_weight": vals.get("shipping_weight", False)})

        if vals.get("weight", False):
            picking_ids = self.env["stock.picking"].search(
                [
                    "&",
                    ("origin", "=", self.origin),
                    ("weight", "!=", vals.get("weight")),
                ],
                limit=1,
            )
            if picking_ids:
                picking_ids.write({"weight": vals.get("weight", False)})
        return res
