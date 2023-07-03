from datetime import datetime,timedelta
from odoo import api, fields, models,_
from odoo.exceptions import UserError

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
            ("pedidos", "Pedidos Ya"),
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
    discount_4 = fields.Boolean()
    
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
            'pedidos': (_('Pedidos Ya'), self.env['delivery.carrier'].search([('name', '=', 'Pedidos Ya')], limit=1)),
            'yummy': (_('Yummy'), self.env['delivery.carrier'].search([('name', '=', 'Yummy')], limit=1))
        }
        if self.shipping_mean in carrier_mapping and self.shipping_method == 'prepaid':
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

    @api.onchange('discount_4')
    def onchange_discount_4(self):
        if self.discount_4:
            for line in self.order_line:
                line.discount = 4