from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "account_retention_line_full")
class TestAccountRetentionLineFull(RetentionTestCommon):

    def test_01_compute_allowed_payment_concept_ids_islr(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "payment_concept_id": self.concept_one.id,
                "invoice_type": "in_invoice", "name": "Test",
                "invoice_amount": 500.0, "invoice_total": 500.0,
                "retention_amount": 15.0,
            })],
        })
        line = retention.retention_line_ids[0]
        line._compute_allowed_payment_concept_ids()
        self.assertTrue(line.allowed_payment_concept_ids)
        self.assertIn(self.concept_one, line.allowed_payment_concept_ids)
        _logger.info("========= test_01 passed =========")

    def test_02_compute_allowed_payment_concept_ids_iva(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": inv.id, "name": "Test",
            "invoice_total": 232.0, "invoice_amount": 200.0,
            "retention_amount": 32.0,
        })
        line._compute_allowed_payment_concept_ids()
        self.assertTrue(line.allowed_payment_concept_ids)
        _logger.info("========= test_02 passed =========")

    def test_03_onchange_move_id_returns_empty_for_blank_move(self):
        line = self.env["account.retention.line"].new({
            "name": "Test",
        })
        result = line._onchange_move_id()
        self.assertEqual(result, {})
        _logger.info("========= test_03 passed =========")

    def test_04_onchange_move_id_returns_warning_no_tax(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.invoice_line_ids.write({"tax_ids": [Command.clear()]})
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].new({
            "retention_id": retention.id,
            "move_id": inv.id,
        })
        result = line._onchange_move_id()
        self.assertIn("warning", result)
        _logger.info("========= test_04 passed =========")

    def test_05_onchange_move_id_updates_from_tax_group(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].new({
            "retention_id": retention.id,
            "move_id": inv.id,
        })
        line._onchange_move_id()
        self.assertGreater(line.iva_amount, 0)
        _logger.info("========= test_05 passed =========")

    def test_06_compute_related_fields_islr_accumulated(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "payment_concept_id": self.concept_one.id,
                "invoice_type": "in_invoice", "name": "Test",
                "invoice_amount": 500.0, "invoice_total": 500.0,
                "retention_amount": 15.0,
            })],
        })
        line = retention.retention_line_ids[0]
        line._compute_related_fields()
        self.assertGreater(line.related_percentage_fees, 0)
        _logger.info("========= test_06 passed =========")

    def test_07_unlink_retention_line_with_payment(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": inv.id, "name": "Test",
            "invoice_total": 232.0, "invoice_amount": 200.0,
            "retention_amount": 32.0,
        })
        payment = self.env["account.payment"].create({
            "payment_type": "outbound", "partner_type": "supplier",
            "partner_id": self.partner_pnr_75.id,
            "journal_id": self.bank_journal_sup_ret.id,
            "payment_type_retention": "iva",
            "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
            "is_retention": True,
        })
        line.payment_id = payment.id
        line.unlink()
        self.assertFalse(payment.exists())
        _logger.info("========= test_07 passed =========")

    def test_08_get_invoice_paid_amount_not_related_with_retentions(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "payment_concept_id": self.concept_one.id,
                "invoice_type": "in_invoice", "name": "Test",
                "invoice_amount": 500.0, "invoice_total": 500.0,
                "retention_amount": 15.0,
            })],
        })
        line = retention.retention_line_ids[0]
        result = line.get_invoice_paid_amount_not_related_with_retentions()
        self.assertIsNotNone(result)
        _logger.info("========= test_08 passed =========")

    def test_09_get_islr_type_person_id_no_retention(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        line = self.env["account.retention.line"].new({
            "move_id": inv.id,
        })
        type_person = line._get_islr_type_person_id()
        self.assertTrue(type_person)
        _logger.info("========= test_09 passed =========")

    def test_10_get_code_of_retention_no_payment_concept(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        line = self.env["account.retention.line"].create({
            "move_id": inv.id,
            "name": "Test",
            "invoice_amount": 500.0, "invoice_total": 500.0,
            "retention_amount": 15.0,
        })
        code = line._get_code_of_retention()
        self.assertEqual(code, "")
        _logger.info("========= test_10 passed =========")

    def test_11_compute_retention_amount_not_islr_skips(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": inv.id, "name": "Test",
            "invoice_total": 232.0, "invoice_amount": 200.0,
            "retention_amount": 32.0,
        })
        line._compute_retention_amount()
        self.assertAlmostEqual(line.retention_amount, 32.0)
        _logger.info("========= test_11 passed =========")
