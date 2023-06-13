from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    printed = fields.Boolean(
        default=False)
    
    # def print_and_mark_as_printed(self):
    #     report_name = 'binaural_invoice.template_invoice_sale_note_binaural_invoice'
    #     self.ensure_one()
    #     self.env['ir.actions.report']._render_qweb_pdf(report_name, [self.id])
    #     self.write({'printed': True})
    #     return True

    def print_and_mark_as_printed(self):
        report_name = 'binaural_invoice.template_invoice_sale_note_binaural_invoice'
        self.ensure_one()
        self.env['ir.actions.report']._render_qweb_pdf(report_name, [self.id])
        self.write({'printed': True})
        return True

    def action_invoice_sent(self):
        self.ensure_one()
        self.print_and_mark_as_printed()
        return True