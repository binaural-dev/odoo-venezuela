from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    warehouse_operator_ids = fields.One2many("stock.warehouse.operator", "company_id")
