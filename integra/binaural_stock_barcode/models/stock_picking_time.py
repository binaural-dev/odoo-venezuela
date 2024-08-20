from odoo import fields, models


class StockPickingTime(models.Model):
    _name = "stock.picking.time"
    _description = "Save time of take picking"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company.id)
    type = fields.Selection(
        [("start", "Start"), ("pause", "Pause"), ("resume", "Resume"), ("end", "End")]
    )
    pick_id = fields.Many2one("stock.picking")
    employee_id = fields.Many2one("hr.employee")
