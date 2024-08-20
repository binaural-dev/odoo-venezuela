from odoo import api, fields, models


class ReportStockMoveLine(models.Model):
    _inherit = "stock.move.line"

    balance = fields.Float(compute="_compute_balance", store=True)
    origin = fields.Char(store=True)

    @api.depends("qty_done", "location_id", "location_dest_id")
    def _compute_balance(self):
        for line in self:
            line.balance = line.qty_done

            if line.location_id.usage == "internal":
                line.balance *= -1
            if line.location_id.usage == line.location_dest_id.usage:
                line.balance = 0
