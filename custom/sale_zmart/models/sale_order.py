from datetime import datetime,timedelta
from odoo import api, fields, models

class SaleOrderZmart(models.Model):
    _inherit = "sale.order"
    
    shipping_type = fields.Selection(
        [
            ("withdrawal", "withdrawal"),
            ("shipment", "shipment"),
        ],
        default = "withdrawal",
        store = True,
        required = True
    )
    shipping_name_company = fields.Many2one(
        'sale.company', 
        string = "Company"
    )
    priority = fields.Selection(
        [
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
        ],
        default = "low",
        store = True,
        required = True
    )
    printed = fields.Boolean(
        related = 'invoice_ids.printed'
    )
    shipping_method = fields.Selection(
        [
            ("prepaid", "Prepaid"),
            ("free", "Free"),
            ("collect_at_destination", "Collect at Destination"),
        ],
        default = "free",
        store = True
    )
    product_id = fields.Many2one(
        'product.template', 
        string = 'Product'
    )
    
    def button_sale_order(self):
        return self.env.ref('sale.action_report_saleorder').report_action(self)

    @api.onchange('shipping_method')
    def add_product_to_lines(self):
        if self.shipping_method == 'prepaid':
            product = self.env['product.template'].search([('name', '=', 'Cargo por envío')], limit=1)
            if product:
                self.write({
                    'order_line': [(0, 0, {
                        'product_template_id': product.name,
                        'name': product.name,
                        'product_uom_qty': 1,
                        'price_unit': product.list_price,
                    })]
                })