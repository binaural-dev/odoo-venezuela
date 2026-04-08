from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from odoo import fields
from odoo.tests import TransactionCase, tagged
from werkzeug.exceptions import BadRequest

from odoo.addons.l10n_ve_invoice.controllers.accounting_reports import AccountingReportsController


class _FakeRequest:
    def __init__(self, env):
        self.env = env

    def make_response(self, data, headers=None):
        return {"data": data, "headers": headers or []}


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountingReportsController(TransactionCase):
    def setUp(self):
        super().setUp()
        self.controller = AccountingReportsController()
        self.company = self.env.company

    def _create_wizard(self, user=None, report="purchase"):
        vals = {
            "company_id": self.company.id,
            "report": report,
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        }
        model = self.env["wizard.accounting.reports"]
        if user:
            model = model.with_user(user)
        return model.create(vals)

    def test_download_purchase_book_uses_wizard_id(self):
        wizard = self._create_wizard(report="purchase")

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_purchases_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"purchase:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_purchase_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
                wizard_id=str(wizard.id),
            )

        self.assertEqual(response["data"], f"purchase:{wizard.id}:{self.company.id}".encode())
        headers = dict(response["headers"])
        self.assertIn("Libro_de_compra.xlsx", headers.get("Content-Disposition", ""))

    def test_download_sales_book_uses_wizard_id(self):
        wizard = self._create_wizard(report="sale")

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_sales_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"sale:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_sales_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
                wizard_id=str(wizard.id),
            )

        self.assertEqual(response["data"], f"sale:{wizard.id}:{self.company.id}".encode())
        headers = dict(response["headers"])
        self.assertIn("Libro_de_venta.xlsx", headers.get("Content-Disposition", ""))

    def test_download_purchase_book_fallback_to_current_user(self):
        group_user = self.env.ref("base.group_user")
        other_user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Tmp Other User",
                "login": "tmp_other_user_ci",
                "email": "tmp_other_user_ci@example.com",
                "groups_id": [(6, 0, [group_user.id])],
            }
        )

        own_wizard = self._create_wizard(report="purchase")
        self._create_wizard(user=other_user, report="purchase")

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_purchases_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"fallback:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_purchase_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
            )

        self.assertEqual(response["data"], f"fallback:{own_wizard.id}:{self.company.id}".encode())

    def test_download_purchase_book_fallback_uses_purchase_report(self):
        own_purchase_wizard = self._create_wizard(report="purchase")
        self._create_wizard(report="sale")

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_purchases_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"purchase_type:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_purchase_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
            )

        self.assertEqual(
            response["data"],
            f"purchase_type:{own_purchase_wizard.id}:{self.company.id}".encode(),
        )

    def test_download_sales_book_fallback_uses_sale_report(self):
        own_sale_wizard = self._create_wizard(report="sale")
        self._create_wizard(report="purchase")

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_sales_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"sale_type:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_sales_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
            )

        self.assertEqual(
            response["data"],
            f"sale_type:{own_sale_wizard.id}:{self.company.id}".encode(),
        )

    def test_download_purchase_book_fallback_uses_same_company(self):
        company_2 = self.env["res.company"].create({"name": "Tmp Company 2"})
        own_purchase_wizard = self._create_wizard(report="purchase")
        self.env["wizard.accounting.reports"].create(
            {
                "company_id": company_2.id,
                "report": "purchase",
                "date_from": fields.Date.today(),
                "date_to": fields.Date.today(),
            }
        )

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_purchases_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"purchase_company:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_purchase_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
            )

        self.assertEqual(
            response["data"],
            f"purchase_company:{own_purchase_wizard.id}:{self.company.id}".encode(),
        )

    def test_download_sales_book_fallback_uses_same_company(self):
        company_2 = self.env["res.company"].create({"name": "Tmp Company 3"})
        own_sale_wizard = self._create_wizard(report="sale")
        self.env["wizard.accounting.reports"].create(
            {
                "company_id": company_2.id,
                "report": "sale",
                "date_from": fields.Date.today(),
                "date_to": fields.Date.today(),
            }
        )

        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), patch(
            "odoo.addons.l10n_ve_invoice.wizard.accounting_reports.WizardAccountingReportsBinauralInvoice.generate_sales_book",
            autospec=True,
            side_effect=lambda wiz, company_id: f"sale_company:{wiz.id}:{company_id}".encode(),
        ):
            response = self.controller.download_sales_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
            )

        self.assertEqual(
            response["data"],
            f"sale_company:{own_sale_wizard.id}:{self.company.id}".encode(),
        )

    def test_download_purchase_book_rejects_invalid_company_id(self):
        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), self.assertRaises(BadRequest):
            self.controller.download_purchase_book.__wrapped__(
                self.controller,
                company_id="abc",
            )

    def test_download_sales_book_rejects_invalid_wizard_id(self):
        with patch(
            "odoo.addons.l10n_ve_invoice.controllers.accounting_reports.http.request",
            _FakeRequest(self.env),
        ), self.assertRaises(BadRequest):
            self.controller.download_sales_book.__wrapped__(
                self.controller,
                company_id=str(self.company.id),
                wizard_id="x1",
            )

    def test_generate_purchase_book_without_moves_exports_zero_resume(self):
        wizard = self._create_wizard(report="purchase")

        content = wizard.generate_purchases_book(self.company)

        self.assertTrue(content.startswith(b"PK"))

        with ZipFile(BytesIO(content)) as workbook_zip:
            sheet_xml = workbook_zip.read("xl/worksheets/sheet1.xml").decode()
            shared_strings = workbook_zip.read("xl/sharedStrings.xml").decode()

        self.assertIn("Compras Internas no Gravadas", shared_strings)
        self.assertIn("Total Compras y Créditos Fiscales del Periodo", shared_strings)
        self.assertGreaterEqual(sheet_xml.count("<v>0</v>"), 8)
