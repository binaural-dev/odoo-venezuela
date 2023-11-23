from odoo import fields, models


class StockWarehouseOperator(models.Model):
    _name = "stock.warehouse.operator"
    _description = "Stock Warehouse Operator"
    _check_company_auto = True

    name = fields.Char(string="Name")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
