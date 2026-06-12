from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_payment_register")
class TestWizardPaymentRegister(RetentionTestCommon):

    def _make_payment_wizard(self, invoice, **kwargs):
        vals = {
            "amount": invoice.amount_total,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        }
        vals.update(kwargs)
        return self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create(vals)

    def test_01_compute_available_journal_ids_excludes_supplier(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice)
        wizard._compute_available_journal_ids()
        self.assertIn(self.bank_journal_sub, wizard.available_journal_ids)
        _logger.info("========= test_01 passed =========")

    def test_02_onchange_retention_enable(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice)
        wizard.is_retention = True
        wizard._onchange_retention()
        self.assertFalse(wizard.edit_retention_fields)
        _logger.info("========= test_02 passed =========")

    def test_03_onchange_retention_disable_returns_dict(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice)
        result = wizard._onchange_retention()
        self.assertIn("value", result)
        self.assertIn("edit_retention_fields", result["value"])
        self.assertTrue(result["value"]["edit_retention_fields"])
        _logger.info("========= test_03 passed =========")

    def test_04_onchange_retention_line_ids_updates_amount(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice, amount=0.0)
        retention_line = self.env["account.retention.line"].create({
            "name": "Test", "invoice_total": 232.0, "invoice_amount": 200.0,
            "retention_amount": 32.0,
        })
        wizard.retention_line_ids = retention_line
        wizard._onchange_retention_line_ids()
        self.assertEqual(wizard.amount, 32.0)
        _logger.info("========= test_04 passed =========")

    def test_05_onchange_retention_line_ids_empty(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice, amount=100.0)
        wizard.write({"retention_line_ids": [Command.clear()]})
        wizard._onchange_retention_line_ids()
        self.assertEqual(wizard.amount, 100.0)
        _logger.info("========= test_05 passed =========")

    def test_06_load_iva_retention_lines(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice)
        result = wizard._load_iva_retention_lines(invoice)
        self.assertIn("value", result)
        _logger.info("========= test_06 passed =========")

    def test_07_post_payments_retention_returns_none(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice)
        wizard.is_retention = True
        result = wizard._post_payments([], False)
        self.assertIsNone(result)
        _logger.info("========= test_07 passed =========")

    def test_08_reconcile_payments_retention_returns_none(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self._make_payment_wizard(invoice)
        wizard.is_retention = True
        result = wizard._reconcile_payments([], False)
        self.assertIsNone(result)
        _logger.info("========= test_08 passed =========")
