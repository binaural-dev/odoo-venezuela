from odoo.http import request, route, content_disposition
from odoo.tools.safe_eval import safe_eval
from PyPDF2 import PdfFileReader, PdfFileWriter
from odoo.tools.misc import format_date


from odoo.addons.hr_payroll.controllers.main import HrPayroll


import io
import re
import datetime


class HrPayroll(HrPayroll):

    @route(["/print/payslips"], type='http', auth='user')
    def get_payroll_report_print(self, list_ids='', **post):
        if not request.env.user.has_group('hr_payroll.group_hr_payroll_user') or not list_ids or re.search("[^0-9|,]", list_ids):
            return request.not_found()

        ids = [int(s) for s in list_ids.split(',')]
        payslips = request.env['hr.payslip'].browse(ids)

        pdf_writer = PdfFileWriter()
        payslip_reports = payslips._get_pdf_reports()

        for report, slips in payslip_reports.items():
            for payslip in slips:
                pdf_content, _ = request.env['ir.actions.report'].\
                    with_context(lang=payslip.employee_id.sudo().address_home_id.lang).\
                    sudo().\
                    _render_qweb_pdf(report, payslip.id, data={'company_id': payslip.company_id})
                reader = PdfFileReader(io.BytesIO(pdf_content), strict=False, overwriteWarnings=False)

                for page in range(reader.getNumPages()):
                    pdf_writer.addPage(reader.getPage(page))

        _buffer = io.BytesIO()
        pdf_writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()

        lang = payslips.employee_id.sudo().address_home_id.lang

        report_name = '%s - %s - %s - %s' % ('Nómina', payslips.struct_id.name, payslips.employee_id.name, format_date(request.env, payslips.date_from, date_format="MMMM y", lang_code=lang))
        
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(merged_pdf)),
            ('Content-Disposition', content_disposition(report_name + '.pdf'))
        ]

        return request.make_response(merged_pdf, headers=pdfhttpheaders)
