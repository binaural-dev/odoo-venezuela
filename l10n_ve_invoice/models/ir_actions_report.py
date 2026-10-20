from odoo import _, models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        report = self._get_report(report_ref) if report_ref else None
        if report and res_ids and report.model == 'account.move':
            docs = self.env['account.move'].browse(res_ids)
            valid = docs.filtered(lambda d: d.state == 'posted')
            if not valid:
                raise UserError(_(
                    "None of the selected documents are posted.\n"
                    "Only posted documents can be printed."
                ))
            res_ids = valid.ids
        if report and res_ids and report.model == 'sale.order':
            docs = self.env['sale.order'].browse(res_ids)
            valid = docs.filtered(lambda d: d.state != 'draft')
            if not valid:
                raise UserError(_(
                    "None of the selected sale orders are confirmed.\n"
                    "Only non-draft orders can be printed."
                ))
            res_ids = valid.ids
        return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

    def _render_qweb_html(self, report_ref, docids, data=None):
        report = self._get_report(report_ref)
        model = report.model
        ids = docids
        if data and data.get('context'):
            ids = data['context'].get('active_ids') or docids
            model = data['context'].get('active_model') or report.model
        if model == 'account.move' and ids:
            docs = self.env[model].browse(ids)
            valid = docs.filtered(lambda d: d.state == 'posted')
            if not valid:
                raise UserError(_(
                    "None of the selected documents are posted.\n"
                    "Only posted documents can be printed."
                ))
            return super()._render_qweb_html(report_ref, valid.ids, data=data)
        if model == 'sale.order' and ids:
            docs = self.env[model].browse(ids)
            valid = docs.filtered(lambda d: d.state != 'draft')
            if not valid:
                raise UserError(_(
                    "None of the selected sale orders are confirmed.\n"
                    "Only non-draft orders can be printed."
                ))
            return super()._render_qweb_html(report_ref, valid.ids, data=data)
        return super()._render_qweb_html(report_ref, docids, data=data)
