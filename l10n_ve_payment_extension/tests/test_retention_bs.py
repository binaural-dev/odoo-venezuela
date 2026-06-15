from odoo.tests import tagged
from odoo import Command, fields
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_accounting_reports_expanded")
class TestWizardAccountingReportsExpanded(RetentionTestCommon):

    def _make_iva_invoice_with_retention(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.generate_iva_retention = True
        inv.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        if retention and retention.state != "emitted":
            retention.action_post()
        return inv

    def _make_wizard(self, report_type="purchase"):
        return self.env["wizard.accounting.reports"].create({
            "report": report_type,
            "date_from": fields.Date.subtract(fields.Date.today(), days=30),
            "date_to": fields.Date.today(),
            "company_id": self.company.id,
        })

    def test_01_determinate_resume_retention_books(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        result = wizard._determinate_resume_retention_books(inv)
        self.assertEqual(len(result), 4)
        self.assertIsInstance(result[1], float)
        _logger.info("========= test_01 passed =========")

    def test_02_determinate_resume_retention_books_no_retention_moves(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        result = wizard._determinate_resume_retention_books(inv)
        self.assertEqual(len(result), 4)
        _logger.info("========= test_02 passed =========")

    def test_03_search_moves_with_retentions(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        moves = wizard.search_moves()
        self.assertIn(inv, moves)
        _logger.info("========= test_03 passed =========")

    def test_04_get_retention_iva_values(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        values = wizard.get_retention_iva_values(inv.id)
        self.assertIn("date_retention", values)
        self.assertIn("number_retention", values)
        self.assertIn("iva_retained", values)
        _logger.info("========= test_04 passed =========")

    def test_05_get_retention_domain(self):
        wizard = self._make_wizard("purchase")
        domain = wizard._get_retention_domain()
        self.assertIn(("type_retention", "=", "iva"), domain)
        self.assertIn(("state", "=", "emitted"), domain)
        _logger.info("========= test_05 passed =========")

    def test_06_sum_retention_total(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        lines = inv.retention_iva_line_ids
        total = wizard._sum_retention_total(lines)
        self.assertGreaterEqual(total, 0)
        _logger.info("========= test_06 passed =========")

    def test_07_check_future_retention_dates(self):
        wizard = self._make_wizard("purchase")
        result = wizard._check_future_retention_dates(fields.Date.today())
        self.assertFalse(result)
        _logger.info("========= test_07 passed =========")

    def test_08_resume_sale_book_fields(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("sale")
        result = wizard._resume_sale_book_fields(inv)
        self.assertTrue(any("Total Retenciones" in str(r.get("name", "")) for r in result))
        _logger.info("========= test_08 passed =========")

    def test_09_resume_purchase_book_fields(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        result = wizard._resume_purchase_book_fields(inv)
        self.assertTrue(any("Total Retenciones" in str(r.get("name", "")) for r in result))
        _logger.info("========= test_09 passed =========")

    def test_10_get_retention_iva_values_no_retention(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        wizard = self._make_wizard("purchase")
        values = wizard.get_retention_iva_values(inv.id)
        self.assertEqual(values["iva_retained"], 0)
        _logger.info("========= test_10 passed =========")
