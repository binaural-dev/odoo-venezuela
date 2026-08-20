import csv
import io
import json

from odoo import _
from odoo.http import request, route, content_disposition
from odoo.addons.product.controllers.pricelist_report import ProductPricelistExportController


class ProductPricelistExportController(ProductPricelistExportController):
    """Override the native single-pricelist CSV/XLSX export: our
    ``_get_report_data`` returns a `pricelists` recordset and a `prices`
    dict per product (keyed by pricelist id) instead of the native
    `pricelist`/`quantities`/`price` shape, so the row/column building
    below has to match that instead of the base implementation.

    The export always covers every product in `active_ids` — callers
    (our JS) never send `page`/`page_size` here, mirroring the PDF export.
    """

    @route('/product/export/pricelist/', type='http', auth='user', readonly=True)
    def export_pricelist(self, report_data, export_format):
        json_data = json.loads(report_data)
        report_data = request.env['report.product.report_pricelist']._get_report_data(json_data)
        pricelists = report_data['pricelists']
        products = report_data['products']
        headers = [_("Product"), _("UOM")] + [pricelist.display_name for pricelist in pricelists]
        if export_format == 'csv':
            return self._generate_csv(pricelists, products, headers)
        return self._generate_xlsx(pricelists, products, headers)

    def _generate_rows(self, products, pricelists):
        rows = []
        for product in products:
            variants = product.get('variants') or [product]
            for variant in variants:
                row = [variant['name'], variant['uom']] + [
                    variant['prices'].get(pricelist.id, 0.0) for pricelist in pricelists
                ]
                rows.append(row)
        return rows

    def _generate_csv(self, pricelists, products, headers):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(self._generate_rows(products, pricelists))
        content = buffer.getvalue()
        buffer.close()
        response_headers = [
            ('Content-Type', 'text/csv'),
            ('Content-Disposition', content_disposition('Pricelist.csv')),
        ]
        return request.make_response(content, response_headers)

    def _generate_xlsx(self, pricelists, products, headers):
        buffer = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.write_row(0, 0, headers)
        rows = self._generate_rows(products, pricelists)
        column_widths = [len(str(header)) for header in headers]
        for row_idx, row in enumerate(rows, start=1):
            worksheet.write_row(row_idx, 0, row)
            for col_idx, cell_value in enumerate(row):
                column_widths[col_idx] = max(column_widths[col_idx], len(str(cell_value)))

        for col_idx, width in enumerate(column_widths):
            worksheet.set_column(col_idx, col_idx, width)
        workbook.close()
        content = buffer.getvalue()
        buffer.close()
        response_headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition('Pricelist.xlsx')),
        ]
        return request.make_response(content, response_headers)
