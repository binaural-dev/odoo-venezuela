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
    shipping_mean = fields.Selection(
        [
            ("zmart_express", "Zmart Express"),
            ("zmart_programado", "Zmart Programado"),
            ("liberty_express", "Liberty Express"),
            ("mrw", "MRW"),
            ("tealca", "Tealca"),
            ("zoom", "Zoom"),
            ("domesa", "Domesa"),
            ("pedidos", "Pedidos"),
            ("yummy", "Yummy"),
        ],
        default = "",
        store = True
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
    unlock_date = fields.Date(string='Unlock Date', readonly=True)
    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order.unlock_date = (datetime.today() + timedelta(days=2)).date()
        return res

    def action_cancel_if_no_invoice(self):
        orders = self.search([('state', '=', 'sale'),('invoice_status','=','invoiced'), ('unlock_date', '<=', fields.Date.today())])
        for order in orders:
            if not order.invoice_ids:
                order.action_cancel()


    def send_cancel_warning_email(self):
        for order in self:
            if order.user_id and order.partner_id.email:
                template = self.env.ref('sale_zmart.email_template_cancel_warning')
                template.with_context(order=order).send_mail(order.user_id.id, force_send=True)
    
    def button_sale_order(self):
        return self.env.ref('sale.action_report_saleorder').report_action(self)
    
    
    @api.onchange('shipping_method', 'shipping_mean')
    def add_product_to_lines(self):
        if self.shipping_method == 'prepaid':
            shipping_lines = {
                'zmart_express': {'default_code': 'EXP',},
                'zmart_programado': {'default_code': 'PRG',},
                'liberty_express': {'default_code': 'LIB',},
                'mrw': {'default_code': 'MRW',},
                'tealca': {'default_code': 'TEA',},
                'zoom': {'default_code': 'ZOO',},
                'domesa': { 'default_code': 'DOM',},
                'pedidos': {'default_code': 'PYA',},
                'yummy': {'default_code': 'YUM',},
            }
            line_data = shipping_lines.get(self.shipping_mean)
            if line_data:
                product = self.env['product.template'].search([('default_code', '=', line_data['default_code'])], limit=1)
                if product:
                    self.write({
                        'order_line': [(0, 0, {
                            'product_template_id': product.name,
                            'name': product.name,
                            'product_uom_qty': 1,
                            'price_unit': product.list_price,
                        })]
                    })
                
    class MailTemplate(models.Model):
        _inherit = 'mail.template'

    @api.model
    def send_cancel_warning_email(self, order_id):
        order = self.env['sale.order'].browse(order_id)
        if order.user_id and order.partner_id.email:
            template = self.env.ref('sale_zmart.email_template_cancel_warning')
            template.with_context(order=order).send_mail(order.user_id.id, force_send=True)