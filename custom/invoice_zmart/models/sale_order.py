from datetime import datetime,timedelta
from odoo import api, fields, models

class SaleOrderZmart(models.Model):
    _inherit = "sale.order"
    
    shipping_name_company = fields.Many2one(
        'sale.company', 
        string = "Company"
    )