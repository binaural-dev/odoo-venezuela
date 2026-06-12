from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "move_retention_protections")
class TestMoveRetentionProtections(RetentionTestCommon):

    def test_01_js_remove_outstanding_partial_blocked(self):
        inv = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.generate_iva_retention = True
        inv.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        self.assertTrue(retention)
        if retention.state != "emitted":
            retention.action_post()
        payment = retention.payment_ids[:1]
        self.assertTrue(payment)
        partial = self.env["account.partial.reconcile"].search([
            ("credit_move_id.move_id", "=", payment.move_id.id),
        ], limit=1)
        if not partial:
            partial = self.env["account.partial.reconcile"].search([
                ("debit_move_id.move_id", "=", payment.move_id.id),
            ], limit=1)
        if partial:
            try:
                inv.js_remove_outstanding_partial(partial.id)
            except (UserError, AttributeError):
                pass
            else:
                self.fail("Expected UserError or AttributeError")
        _logger.info("========= test_01 passed =========")

    def test_02_button_draft_retention_payment_blocked(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        if retention.state != "emitted":
            retention.action_post()
        payment = retention.payment_ids[:1]
        self.assertTrue(payment)
        with self.assertRaises(UserError):
            payment.move_id.button_draft()
        _logger.info("========= test_02 passed =========")

    def test_03_button_draft_bypass_ok(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        self.assertTrue(invoice.state == "posted")
        invoice.with_context(bypass_retention_lock=True).button_draft()
        self.assertEqual(invoice.state, "draft")
        _logger.info("========= test_03 passed =========")

    def test_04_compute_payments_widget_reconciled_info(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.generate_iva_retention = True
        invoice.action_post()
        result = invoice._compute_payments_widget_reconciled_info()
        self.assertIsNone(result)
        _logger.info("========= test_04 passed =========")


    def test_07_get_retention_journals(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        journals = invoice._get_retention_journals(True)
        self.assertIn("iva", journals)
        self.assertIn("municipal", journals)
        _logger.info("========= test_07 passed =========")

    

    def test_09_prepare_retention_vals_iva(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        payment = self.env["account.payment"].create({
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_pnr_75.id,
            "journal_id": self.bank_journal_sup_ret.id,
            "payment_type_retention": "iva",
            "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
            "is_retention": True,
        })
        vals = invoice._prepare_retention_vals("iva", payment)
        self.assertIn("retention_line_ids", vals)
        _logger.info("========= test_09 passed =========")

    def test_10_validate_payment_retention_returns_false(self):
        result = self.env["account.move"].validate_payment({"is_retention": True})
        self.assertFalse(result)
        _logger.info("========= test_10 passed =========")

    def test_11_validate_payment_non_retention_returns_true(self):
        result = self.env["account.move"].validate_payment({"is_retention": False})
        self.assertTrue(result)
        _logger.info("========= test_11 passed =========")

    def test_12_action_register_payment_sets_context_supplier(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        res = invoice.action_register_payment()
        self.assertIn("context", res)
        self.assertIn("default_is_out_invoice", res["context"])
        self.assertFalse(res["context"]["default_is_out_invoice"])
        _logger.info("========= test_12 passed =========")

    def test_13_compute_count_retentions(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        invoice.compute_count_retentions()
        self.assertIsInstance(invoice.count_iva_retention, int)
        self.assertIsInstance(invoice.count_islr_retention, int)
        _logger.info("========= test_13 passed =========")

    def test_14_compute_state_retentions_lines(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        invoice._compute_state_retentions_lines()
        self.assertFalse(invoice.not_edit_islr_retention_lines)
        _logger.info("========= test_14 passed =========")

    def test_15_compute_currency_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice._compute_currency_fields()
        self.assertTrue(invoice.base_currency_is_vef)
        _logger.info("========= test_15 passed =========")

    def test_16_validate_iva_retention_missing_journal(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.company.write({"iva_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            invoice._validate_iva_retention()
        _logger.info("========= test_16 passed =========")

    def test_17_validate_iva_retention_no_taxes_raises(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.invoice_line_ids.write({"tax_ids": [Command.clear()]})
        with self.assertRaises(UserError):
            invoice._validate_iva_retention()
        _logger.info("========= test_17 passed =========")

    def test_18_validate_municipal_no_journal(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.company.write({"municipal_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            invoice._validate_municipal_retention()
        _logger.info("========= test_18 passed =========")

    def test_19_validate_municipal_retention_raises(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        with self.assertRaises(UserError):
            invoice._validate_municipal_retention()
        _logger.info("========= test_19 passed =========")
