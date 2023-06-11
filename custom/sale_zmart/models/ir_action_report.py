from odoo import models, fields, api
    
    
class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'
    
    def _render_qweb_pdf(self, report_name, docids, data=None):
        res = super()._render_qweb_pdf(report_name, docids, data=data)
        if self._get_report(report_name).report_name in ('account.report_invoice_with_payments', 'account.report_invoice'):
            invoices = self.env['account.move'].browse(docids)
            invoices.write({'printed': True})
        return res