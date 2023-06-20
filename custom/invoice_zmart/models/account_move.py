from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    printed = fields.Boolean(default=False)
    # sale_order_shipping_name_company = fields.Many2one(
    #     'sale.company', string = 'Sale Order Shipping Company', 
    #     compute = '_compute_sale_order_shipping_name_company', 
    #     store = True
    # )
    
    def button_free_form(self):
        return self.env.ref('binaural_invoice.action_invoice_free_form_binaural_invoice').report_action(self)
    
    def button_invoice_sale_note(self):
        return self.env.ref('binaural_invoice.action_invoice_sale_note_binaural_invoice').report_action(self)
    
    def button_invoice_sale_note_bs(self):
        return self.env.ref('invoice_zmart.action_invoice_sale_note_bs').report_action(self)
    
   

    # @api.depends('line_ids.sale_line_ids.order_id.shipping_name_company')
    # def _compute_sale_order_shipping_name_company(self):
    #     for move in self:
    #         sale_order = move.line_ids.mapped('sale_line_ids.order_id')
    #         if len(sale_order) == 1:
    #             move.sale_order_shipping_name_company = sale_order.shipping_name_company
    #         else:
    #             move.sale_order_shipping_name_company = False