from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    printed = fields.Boolean(default=False)
    
    def button_free_form(self):
        self.write({'printed': True})
        return self.env.ref('binaural_invoice.action_invoice_free_form_binaural_invoice').report_action(self)
    
    def button_free_form_usd(self):
        self.write({'printed': True})
        return self.env.ref('binaural_invoice.action_invoice_free_form_binaural_invoice').report_action(self)
    
    def button_invoice_sale_note(self):
        return self.env.ref('binaural_invoice.action_invoice_sale_note_binaural_invoice').report_action(self)
    
    def button_invoice_sale_note_bs(self):
        return self.env.ref('invoice_zmart.action_invoice_sale_note_bs').report_action(self)