from datetime import datetime,timedelta
from odoo import api, fields, models

class SaleOrderZmart(models.Model):
    _inherit = "sale.order"
    
    shipping_mean = fields.Selection(
        related='sale_id.shipping_mean'
    )    