from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch
import zipfile

from odoo import fields
from odoo.tests import HttpCase, TransactionCase, tagged



@tagged('bin', 'l10n_ve_stock_reports', '-at_install', 'post_install')
class TestStockBookReportController(HttpCase):

    def test_download_stock_book_route_returns_binary(self):
        """Test that the /web/download_stock_book route returns the binary data from the generate_stocks_book method."""
        self.env["wizard.stock.book.report"].create({
            "company_id": self.env.company.id,
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today() + timedelta(days=1),
        })
        with patch(
            "odoo.addons.l10n_ve_stock_reports.wizard.stock_book_report.WizardStockBookReport.generate_stocks_book",
            return_value=b"datos",
        ) as mocked_generate:
            self.authenticate("admin", "admin")
            response = self.url_open(
                "/web/download_stock_book?company_id=%s" % self.env.company.id
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Content-Type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment;filename=Libro_de_Inventario.xlsx", response.headers.get("Content-Disposition"))
        self.assertEqual(response.content, b"datos")
        mocked_generate.assert_called_once_with(self.env.company.id)
