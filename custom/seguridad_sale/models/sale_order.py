from datetime import datetime,timedelta
from odoo import api, fields, models,_
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    shipping_method = fields.Many2one(
        'sale.shipping.method'
    )