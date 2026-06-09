from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_payment_register_full")
class TestWizardPaymentRegisterFull(RetentionTestCommon):

    def _make_invoice(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "out_invoice", self.sale_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        return inv

    def _make_wizard(self, invoice, **kw):
        vals = {
            "amount": invoice.amount_total,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        }
        vals.update(kw)
        return self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create(vals)

    def test_01_load_iva_retention_lines(self):
        inv = self._make_invoice()
        wizard = self._make_wizard(inv)
        wizard.is_retention = True
        lines = wizard._load_iva_retention_lines(inv)
        self.assertIn("value", lines)
        self.assertIn("retention_line_ids", lines["value"])
        _logger.info("========= test_01 passed =========")

    def test_02_load_iva_retention_lines_no_taxes_raises(self):
        inv = self._make_invoice()
        inv.invoice_line_ids.write({"tax_ids": [Command.clear()]})
        wizard = self._make_wizard(inv)
        result = wizard._load_iva_retention_lines(inv)
        self.assertIn("warning", result)
        self.assertIn("is_retention", result["value"])
        self.assertFalse(result["value"]["is_retention"])
        _logger.info("========= test_02 passed =========")

    def test_03_load_iva_retention_lines_emitted_retention_raises(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.generate_iva_retention = True
        inv.action_post()
        wizard = self._make_wizard(inv, journal_id=self.bank_journal_sup_ret.id)
        result = wizard._load_iva_retention_lines(inv)
        self.assertIn("warning", result)
        _logger.info("========= test_03 passed =========")

    def test_04_create_retention_method_direct(self):
        inv = self._make_invoice()
        wizard = self._make_wizard(inv, voucher_date=fields.Date.today(), retention_ref="TEST123")
        wizard.is_retention = True
        payments = self.env["account.payment"].create([{
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_pnr_75.id,
            "journal_id": self.bank_journal_sub.id,
            "payment_type_retention": "iva",
            "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
            "is_retention": True,
            "amount": 32.0,
        }])
        retention = wizard._create_retention(payments)
        self.assertTrue(retention)
        self.assertEqual(retention.type_retention, "iva")
        self.assertEqual(retention.state, "draft")
        _logger.info("========= test_04 passed =========")

    def test_05_onchange_retention_enables_journal_and_lines(self):
        inv = self._make_invoice()
        wizard = self._make_wizard(inv, journal_id=self.bank_journal_sub.id)
        wizard.is_retention = True
        result = wizard._onchange_retention()
        if result and "value" in result:
            self.assertIn("retention_line_ids", result["value"])
        self.assertFalse(wizard.edit_retention_fields)
        _logger.info("========= test_05 passed =========")

    def test_06_onchange_retention_disabled_clears(self):
        inv = self._make_invoice()
        wizard = self._make_wizard(inv)
        result = wizard._onchange_retention()
        self.assertIn("value", result)
        self.assertTrue(result["value"]["edit_retention_fields"])
        _logger.info("========= test_06 passed =========")

    def test_07_post_payments_retention_returns_none(self):
        inv = self._make_invoice()
        wizard = self._make_wizard(inv)
        wizard.is_retention = True
        result = wizard._post_payments([], False)
        self.assertIsNone(result)
        _logger.info("========= test_07 passed =========")

    def test_08_reconcile_payments_retention_returns_none(self):
        inv = self._make_invoice()
        wizard = self._make_wizard(inv)
        wizard.is_retention = True
        result = wizard._reconcile_payments([], False)
        self.assertIsNone(result)
        _logger.info("========= test_08 passed =========")
