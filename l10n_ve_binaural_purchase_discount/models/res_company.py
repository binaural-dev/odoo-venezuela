from odoo import fields, models

class Company(models.Model):
    _inherit = 'res.company'

    purchase_discount_product_id = fields.Many2one(
        comodel_name='product.product',
        string="Discounted Product",
        domain=[
            ('type', '=', 'service'),
            ('purchase_method', '=', 'purchase')
        ],
        help="Default product used for discounts",
        check_company=True,
    )