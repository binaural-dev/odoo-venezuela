from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from .test_withholding_common_VEF import RetentionTestCommon
import logging
import base64

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "account_retention_advanced")
class TestAccountRetentionAdvanced(RetentionTestCommon):

    def _make_iva_retention_with_invoice(self, invoice):
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        if retention and retention.state != "emitted":
            retention.action_post()
        return retention

    def _make_full_iva_retention(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        return self._make_iva_retention_with_invoice(invoice)

    def test_01_clear_retention_new_lines(self):
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": self._create_invoice_reten_iva(
                    200, self.partner_pnr_75, "in_invoice", self.purchase_journal
                ).id,
                "name": "Test Line", "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0,
            })],
        })
        self.assertTrue(retention.retention_line_ids)
        retention.clear_retention()
        self.assertFalse(retention.retention_line_ids)
        _logger.info("========= test_01 passed =========")

    def test_02_validate_islr_retention_fields_type_person(self):
        partner_no_type = self.env["res.partner"].create({
            "name": "No Type", "vat": "J999",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
        })
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": partner_no_type.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        with self.assertRaises(UserError):
            retention._validate_islr_retention_fields()
        _logger.info("========= test_02 passed =========")

    def test_03_validate_islr_retention_fields_no_concept(self):
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        with self.assertRaises(UserError):
            retention._validate_islr_retention_fields()
        _logger.info("========= test_03 passed =========")

    def test_04_set_sequence_iva(self):
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        retention._set_sequence()
        self.assertTrue(retention.number)
        self.assertTrue(retention.name)
        _logger.info("========= test_04 passed =========")

    def test_05_set_sequence_islr(self):
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        retention._set_sequence()
        self.assertTrue(retention.number)
        _logger.info("========= test_05 passed =========")

    def test_06_set_sequence_municipal(self):
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        retention._set_sequence()
        self.assertTrue(retention.number)
        _logger.info("========= test_06 passed =========")

    def test_07_get_signature_no_config(self):
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        sig = retention.get_signature()
        self.assertFalse(sig)
        _logger.info("========= test_07 passed =========")

    def test_08_get_signature_with_config(self):
        existing = self.env["signature.config"].search([
            ("company_id", "=", self.company.id),
        ])
        sig_b64 = base64.b64encode(b"test_signature_data")
        if existing:
            existing.write({"active": True, "signature": sig_b64})
        else:
            self.env["signature.config"].create({
                "company_id": self.company.id, "active": True,
                "signature": sig_b64,
            })
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        sig = retention.get_signature()
        self.assertTrue(sig)
        _logger.info("========= test_08 passed =========")

    def test_09_compute_retention_lines_data_no_taxes(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.invoice_line_ids.write({"tax_ids": [Command.clear()]})
        try:
            self.env["account.retention"].compute_retention_lines_data(invoice)
        except (UserError, AttributeError):
            pass
        else:
            self.fail("Expected UserError or AttributeError")
        _logger.info("========= test_09 passed =========")

    def test_10_compute_retention_lines_data_iva_supplier(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.generate_iva_retention = True
        invoice.action_post()
        lines_data = self.env["account.retention"].compute_retention_lines_data(
            invoice, self.env["account.payment"]
        )
        self.assertTrue(lines_data)
        self.assertIn("retention_amount", lines_data[0])
        _logger.info("========= test_10 passed =========")

    def test_11_unlink_emitted_raises(self):
        retention = self._make_full_iva_retention()
        self.assertTrue(retention)
        with self.assertRaises(ValidationError):
            retention.unlink()
        _logger.info("========= test_11 passed =========")

    def test_12_action_draft_retention(self):
        retention = self._make_full_iva_retention()
        self.assertTrue(retention)
        self.assertEqual(retention.state, "emitted")
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        retention.action_draft()
        self.assertEqual(retention.state, "draft")
        _logger.info("========= test_12 passed =========")

    def test_13_action_cancel_draft_retention(self):
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        _logger.info("========= test_13 passed =========")

    def test_14_default_get_islr_lines(self):
        invoice = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        ctx = {
            "default_islr_lines": [(self.concept_one.id, 500.0, invoice.invoice_line_ids[0].id)],
            "default_invoice_id": invoice.id,
            "default_type": "in_invoice",
        }
        defaults = self.env["account.retention"].with_context(ctx).default_get(["retention_line_ids"])
        self.assertIn("retention_line_ids", defaults)
        _logger.info("========= test_14 passed =========")

    def test_15_default_get_multi(self):
        invoice = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        ctx = {
            "default_islr_lines": [(self.concept_one.id, 500.0, invoice.invoice_line_ids[0].id)],
            "default_invoice_id": invoice.id,
            "default_type": "in_invoice",
            "multi": True,
        }
        defaults = self.env["account.retention"].with_context(ctx).default_get(["retention_line_ids"])
        self.assertIn("retention_line_ids", defaults)
        _logger.info("========= test_15 passed =========")

    def test_16_action_cancel_with_payments(self):
        retention = self._make_full_iva_retention()
        self.assertTrue(retention)
        self.assertTrue(retention.payment_ids)
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        _logger.info("========= test_16 passed =========")

    def test_17_load_retention_lines_iva_supplier(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        result = retention._load_retention_lines_for_iva_supplier_retention()
        self.assertIn("value", result)
        self.assertIn("retention_line_ids", result["value"])
        _logger.info("========= test_17 passed =========")

    def test_18_validate_retention_journals_iva_supplier(self):
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        self.company.write({"iva_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            retention._validate_retention_journals()
        _logger.info("========= test_18 passed =========")

    def test_19_validate_retention_journals_islr_supplier(self):
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        self.company.write({"islr_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            retention._validate_retention_journals()
        _logger.info("========= test_19 passed =========")

    def test_20_validate_retention_journals_municipal_supplier(self):
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        self.company.write({"municipal_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            retention._validate_retention_journals()
        _logger.info("========= test_20 passed =========")
