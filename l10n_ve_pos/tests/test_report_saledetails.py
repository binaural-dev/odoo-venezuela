from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "report_saledetails")
class ReportSaleDetailsTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.report = cls.env["report.point_of_sale.report_saledetails"]

    def _patch_parent(self, model_name, method_name, **kwargs):
        model_class = self.env[model_name].__class__
        for klass in model_class.__mro__[1:]:
            if method_name in klass.__dict__:
                return patch.object(klass, method_name, **kwargs)
        return patch.object(model_class.__bases__[0], method_name, **kwargs)

    def test_01_get_sale_details_with_session_ids(self):
        with self._patch_parent("report.point_of_sale.report_saledetails", "get_sale_details", return_value={
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
        }):
            result = self.report.get_sale_details(session_ids=[1])
            self.assertEqual(result["total_paid"], 0.0)
            self.assertEqual(result["foreign_total_paid"], 0.0)

    def test_02_get_sale_details_with_date_range(self):
        with self._patch_parent("report.point_of_sale.report_saledetails", "get_sale_details", return_value={
            "date_start": False,
            "date_stop": False,
            "currency_precision": 2,
            "total_paid": 0.0,
            "foreign_total_paid": 0.0,
            "payments": [],
            "currency": self.company.currency_id,
            "foreign_currency": self.company.foreign_currency_id,
            "company_name": self.company.name,
            "taxes": [],
            "products": [],
        }):
            result = self.report.get_sale_details(
                date_start="2024-01-01 00:00:00",
                date_stop="2024-01-31 23:59:59",
            )
            self.assertIn("total_paid", result)
