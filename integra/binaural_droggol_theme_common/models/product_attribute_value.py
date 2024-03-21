
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ProductAttribute(models.Model):
    _name = 'product.attribute.value'
    _inherit = ['product.attribute.value', 'dr.cache.mixin']
    _check_company_auto = True


    active = fields.Boolean("Active", default=True)
    company_id = fields.Many2one(
            "res.company",
            string="Company",
            required=True,
            readonly=True,
            default=lambda self: self.env.company,
        )
