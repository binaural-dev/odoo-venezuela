from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    max_product_invoice = fields.Integer(default=23)
    group_sales_invoicing_series = fields.Boolean()
