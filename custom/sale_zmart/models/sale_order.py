from datetime import datetime,timedelta
from odoo import api, fields, models,_
import logging
_logger = logging.getLogger(__name__)

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
    priority_sale = fields.Selection(
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
    
    def action_open_delivery_wizard(self):
        super().action_open_delivery_wizard()
        view_id = self.env.ref('delivery.choose_delivery_carrier_view_form').id
        carrier_mapping = {
            'zmart_express': (_('Zmart Express'), self.env['delivery.carrier'].search([('name', '=', 'Zmart Express')], limit=1)),
            'zmart_programado': (_('Zmart Programado'), self.env['delivery.carrier'].search([('name', '=', 'Zmart Programado')], limit=1)),
            'liberty_express': (_('Liberty Express'), self.env['delivery.carrier'].search([('name', '=', 'Liberty Express')], limit=1)),
            'mrw': (_('MRW'), self.env['delivery.carrier'].search([('name', '=', 'MRW')], limit=1)),
            'tealca': (_('Tealca'), self.env['delivery.carrier'].search([('name', '=', 'Tealca')], limit=1)),
            'zoom': (_('Zoom'), self.env['delivery.carrier'].search([('name', '=', 'Zoom')], limit=1)),
            'domesa': (_('Domesa'), self.env['delivery.carrier'].search([('name', '=', 'Domesa')], limit=1)),
            'pedidos': (_('Pedidos'), self.env['delivery.carrier'].search([('name', '=', 'Pedidos')], limit=1)),
            'yummy': (_('Yummy'), self.env['delivery.carrier'].search([('name', '=', 'Yummy')], limit=1))
        }
        if self.shipping_mean in carrier_mapping:
            name, carrier = carrier_mapping[self.shipping_mean]
            carrier_id = carrier.id
        else:
            name = _('Add a shipping method')
            partner_shipping = self.with_company(self.company_id).partner_shipping_id
            carrier = (partner_shipping.property_delivery_carrier_id or partner_shipping.commercial_partner_id.property_delivery_carrier_id)
            carrier_id = carrier.id

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.carrier',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_carrier_id': carrier_id,
            }
        }
    class MailTemplate(models.Model):
        _inherit = 'mail.template'

    @api.model
    def send_cancel_warning_email(self, order_id):
        order = self.env['sale.order'].browse(order_id)
        if order.user_id and order.partner_id.email:
            template = self.env.ref('sale_zmart.email_template_cancel_warning')
            template.with_context(order=order).send_mail(order.user_id.id, force_send=True)
            
    