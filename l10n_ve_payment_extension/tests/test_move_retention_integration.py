from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "move_retention_integration")
class TestMoveRetentionIntegration(RetentionTestCommon):

    def _prepare_invoice(self, invoice):
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})

    def test_01_action_post_creates_iva_retention(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.generate_iva_retention = True
        invoice.action_post()
        self.assertTrue(invoice.retention_iva_line_ids)
        _logger.info("========= test_01 passed =========")

    def test_02_action_post_creates_islr_retention(self):
        invoice = self._create_invoice_islr(
            amount=500, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.generate_islr_retention = True
        invoice.action_post()
        self.assertTrue(invoice.retention_islr_line_ids)
        _logger.info("========= test_02 passed =========")

    def test_03_validate_iva_retention_no_journal(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.company.write({"iva_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            invoice._validate_iva_retention()
        _logger.info("========= test_03 passed =========")

    def test_04_validate_municipal_no_journal(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.company.write({"municipal_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            invoice._validate_municipal_retention()
        _logger.info("========= test_04 passed =========")

    def test_05_check_retention_vs_move(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "ISLR Line",
                "invoice_total": 500.0, "invoice_amount": 5000.0,
                "retention_amount": 1000.0, "foreign_invoice_amount": 500.0,
                "foreign_retention_amount": 1000.0,
            })],
        })
        with self.assertRaises(UserError):
            self.env["account.move"]._check_retention_vs_move(retention.retention_line_ids)
        _logger.info("========= test_05 passed =========")

    def test_06_action_view_retention(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        action = invoice.with_context(retention_type="iva").action_view_retention()
        self.assertIn("type", action)
        _logger.info("========= test_06 passed =========")

    def test_07_validate_payment_retention(self):
        result = self.env["account.move"].validate_payment({"is_retention": True})
        self.assertFalse(result)
        _logger.info("========= test_07 passed =========")

    def test_08_prepare_retention_vals(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.action_post()
        vals = invoice._prepare_retention_vals("iva", self.env["account.payment"])
        self.assertIn("retention_line_ids", vals)
        _logger.info("========= test_08 passed =========")
