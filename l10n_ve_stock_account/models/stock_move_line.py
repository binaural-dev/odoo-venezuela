from odoo import models, fields, api


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    qty_invoiced = fields.Float(
        string="Quantity Invoiced", compute="_compute_qty_invoiced", store=True
    )

    @api.depends("product_id", "picking_id")
    def _compute_qty_invoiced(self):
        for line in self:
            invoices = self.env["account.move.line"].search(
                [
                    ("move_id.state", "=", "posted"),
                    ("move_id.invoice_origin", "ilike", line.picking_id.name),
                    ("product_id", "=", line.product_id.id),
                ]
            )
            line.qty_invoiced = sum(invoices.mapped("quantity"))
