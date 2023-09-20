from odoo import api, fields, models, tools, _

class ProductProduct(models.Model):
    _inherit = "product.product"

    is_flete = fields.Boolean("Is flete?", default=False)
    is_other_expense = fields.Boolean("Is other expense?", default=False)
    is_secure = fields.Boolean("Is secure?", default=False)