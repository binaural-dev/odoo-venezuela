from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch, MagicMock
from datetime import datetime


@tagged("post_install", "-at_install", "report_saledetails")
class ReportSaleDetailsTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.report = cls.env["report.point_of_sale.report_saledetails"]

    def test_01_get_sale_details_with_session_ids(self):
        with patch.object(type(self.report), "get_sale_details") as mock:
            mock.return_value = {
                "date_start": None,
                "date_stop": None,
                "currency_precision": 2,
                "total_paid": 0.0,
                "foreign_total_paid": 0.0,
                "payments": [],
                "currency": self.company.currency_id,
                "foreign_currency": self.company.foreign_currency_id,
                "company_name": self.company.name,
                "taxes": [],
                "products": [],
            }
            result = self.report.get_sale_details(session_ids=[1])
            self.assertEqual(result["total_paid"], 0.0)
            self.assertEqual(result["foreign_total_paid"], 0.0)

    def test_02_get_sale_details_with_date_range(self):
        with patch.object(type(self.report), "get_sale_details") as mock:
            mock.return_value = {
                "date_start": datetime.now(),
                "date_stop": datetime.now(),
                "currency_precision": 2,
                "total_paid": 0.0,
                "foreign_total_paid": 0.0,
                "payments": [],
                "currency": self.company.currency_id,
                "foreign_currency": self.company.foreign_currency_id,
                "company_name": self.company.name,
                "taxes": [],
                "products": [],
            }
            result = self.report.get_sale_details(
                date_start="2024-01-01 00:00:00",
                date_stop="2024-01-31 23:59:59",
            )
            self.assertIn("total_paid", result)
