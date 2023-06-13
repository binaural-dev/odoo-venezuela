from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    printed = fields.Boolean(default=False)

    def button_invoice(self):
        return self.env.ref('account.account_invoices').report_action(self)
    
    def button_free_form(self):
        return self.env.ref('binaural_invoice.action_invoice_free_form_binaural_invoice').report_action(self)
    
    def button_invoice_sale_note(self):
        return self.env.ref('binaural_invoice.action_invoice_sale_note_binaural_invoice').report_action(self)
    
    