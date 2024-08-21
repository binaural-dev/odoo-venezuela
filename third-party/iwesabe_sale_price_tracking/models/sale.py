
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def view_last_price(self):
        order_line_ids = self.env['sale.order.line'].search([('id','!=',self.id),
                                                            ('order_id.partner_id','=',self.order_id.partner_id.id),
                                                            ('product_id','=',self.product_id.id)])
        
        if not order_line_ids:
            raise UserError(_("No se ha encontrado una orden para este cliente con este producto!"))
        action = self.env["ir.actions.actions"]._for_xml_id("iwesabe_sale_price_tracking.action_sale_last_price")
        context = {
            'default_sale_line_id':self.id,
        }
        res_id = self.env['sale.last.price'].create({
            'sale_line_id':self.id,
        })
        res_id._compute_body_html()
        action['res_id'] = res_id.id
        action['context'] = context
        return action