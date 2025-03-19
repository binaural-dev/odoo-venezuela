from odoo import models, fields, api


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    qty_invoiced = fields.Float(
        string="Quantity Invoiced", compute="_compute_qty_invoiced", store=True
    )

    date_done = fields.Datetime(string="Date Invoiced", related="picking_id.date_done", store=True)

    guide_number = fields.Char(related="picking_id.guide_number", string="Guide Number", store=True)

    partner_id = fields.Many2one(related="picking_id.partner_id", store=True)

    state_guide_dispatch = fields.Selection(related="picking_id.state_guide_dispatch")

    @api.depends("product_id", "picking_id")
    def _compute_qty_invoiced(self):
        for line in self:
            invoices = self.env["account.move.line"].search(
                [
                    ("move_id.state", "=", "posted"),
                    (
                        "move_id.transfer_ids",
                        "in",
                        [line.picking_id.id],
                    ),
                    ("product_id", "=", line.product_id.id),
                ]
            )
            line.qty_invoiced = sum(invoices.mapped("quantity"))
