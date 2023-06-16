from datetime import datetime,timedelta
from odoo import api, fields, models

class SaleOrderZmart(models.Model):
    _inherit = "sale.order"
    
    shipping_type = fields.Selection(
        [
            ("withdrawal", "withdrawal"),
            ("shipment", "shipment"),
        ],
        default="withdrawal",
        store=True,
        required=True
    )
    name_company = fields.Many2one(
        'sale.company', 
        string="Company"
    )
    priority = fields.Selection(
        [
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
        ],
        default="low",
        store=True,
        required=True
    )
    printed = fields.Boolean(related='invoice_ids.printed')
    shipping_method = fields.Selection(
        [
            ("prepaid", "Prepaid"),
            ("free", "Free"),
            ("collect_at_destination", "Collect at Destination"),
        ],
        default="",
        store=True,
        required=True
    )
    product_id = fields.Many2one('product.template', string='Product')
    unlock_date = fields.Date(string='Unlock Date')

    def action_confirm(self):
        for order in self:
            # Set the unlock date to 7 days from the confirmation date
            unlock_date = datetime.now() + timedelta(days=2)
            order.unlock_date = unlock_date.date()

            # Lock the inventory for the products in the order
            for line in order.order_line:
                line.product_id.virtual_available -= line.product_uom_qty
                line.product_id.outgoing_qty += line.product_uom_qty

            # Call the original confirm function to create the order
            res = super().action_confirm()

            # Schedule the inventory to be unlocked on the unlock date
            order.env['stock.change.product.qty'].sudo().create({
                'product_id': line.product_id.id,
                'location_id': line.order_id.warehouse_id.lot_stock_id.id,
                'new_quantity': line.product_uom_qty,
                'product_uom_id': line.product_uom.id,
                'company_id': order.company_id.id,
                'description': 'Unlock inventory',
                'date': order.unlock_date,
                'action': 'down',
            })

        return res
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