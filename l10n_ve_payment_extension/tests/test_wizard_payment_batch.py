from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "account_move_remaining")
class TestAccountMoveRemaining(RetentionTestCommon):

    def test_01_action_view_retention_islr_single(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.generate_islr_retention = True
        inv.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "islr"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        self.assertTrue(retention)
        action = inv.with_context(retention_type="islr").action_view_retention()
        self.assertEqual(action["res_model"], "account.retention")
        self.assertEqual(action["res_id"], retention.id)
        self.assertEqual(action["view_mode"], "form")
        _logger.info("========= test_01 passed =========")

    def test_02_action_view_retention_municipal_multi(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        ret1 = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "name": "Test", "invoice_total": 232.0,
                "invoice_amount": 200.0, "retention_amount": 5.0,
            })],
        })
        ret2 = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "name": "Test 2", "invoice_total": 232.0,
                "invoice_amount": 200.0, "retention_amount": 3.0,
            })],
        })
        action = inv.with_context(retention_type="municipal").action_view_retention()
        self.assertEqual(action["res_model"], "account.retention")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertIn(ret1.id, action["domain"][0][2])
        self.assertIn(ret2.id, action["domain"][0][2])
        _logger.info("========= test_02 passed =========")

    def test_03_action_view_retention_iva_no_retentions(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        action = inv.with_context(retention_type="iva").action_view_retention()
        self.assertIsNone(action)
        _logger.info("========= test_03 passed =========")

    def test_04_action_post_islr_auto_create(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.generate_islr_retention = True
        inv.action_post()
        self.assertTrue(inv.islr_voucher_number)
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "islr"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        self.assertTrue(retention)
        _logger.info("========= test_04 passed =========")

    def test_05_action_post_islr_no_generate_flag(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        self.assertFalse(inv.islr_voucher_number)
        _logger.info("========= test_05 passed =========")

    def test_06_action_post_iva_supplier_draft_config(self):
        self.company.write({"create_retentions_of_suppliers_in_draft": True})
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.generate_iva_retention = True
        inv.action_post()
        self.assertTrue(inv.iva_voucher_number)
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        self.assertTrue(retention)
        self.assertEqual(retention.state, "draft")
        _logger.info("========= test_06 passed =========")

    def test_07_action_post_municipal_auto_create(self):
        self.company.write({"municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id})
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        eco_act = self.env["economic.activity"].search([], limit=1)
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "name": "Municipal Test",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 5.0,
                "economic_activity_id": eco_act.id if eco_act else False,
            })],
        })
        self.assertTrue(inv.retention_municipal_line_ids)
        inv.action_post()
        self.assertTrue(inv.municipal_voucher_number)
        _logger.info("========= test_07 passed =========")

    def test_08_prepare_retention_vals_islr(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        payment = self.env["account.payment"].create({
            "payment_type": "outbound", "partner_type": "supplier",
            "partner_id": self.partner_pnr_75.id,
            "journal_id": self.bank_journal_sup_ret.id,
            "payment_type_retention": "islr",
            "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
            "is_retention": True,
        })
        vals = inv._prepare_retention_vals("islr", payment)
        self.assertIn("retention_line_ids", vals)
        _logger.info("========= test_08 passed =========")

    def test_09_action_create_islr_from_invoice_single(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        action = inv.action_create_islr_from_invoice()
        self.assertIn("context", action)
        self.assertIn("default_islr_lines", action["context"])
        _logger.info("========= test_09 passed =========")

    def test_10_action_create_islr_from_invoice_multi(self):
        inv1 = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv1.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv1.action_post()
        inv2 = self._create_invoice_islr(
            300, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv2.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv2.action_post()
        action = (inv1 | inv2).action_create_islr_from_invoice()
        self.assertIn("res_model", action)
        self.assertEqual(action["res_model"], "batch.retentions.wizard")
        _logger.info("========= test_10 passed =========")

    def test_11_get_payment_concepts_from_invoice(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        concepts = inv._get_payment_concepts_from_invoice()
        self.assertTrue(concepts)
        concept_id, base_amount, line_id = concepts[0]
        self.assertEqual(concept_id, self.concept_one.id)
        self.assertGreater(base_amount, 0)
        _logger.info("========= test_11 passed =========")

    def test_12_auto_create_islr_retention(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        inv.auto_create_islr_retention()
        self.assertTrue(inv.islr_voucher_number)
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "islr"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        self.assertTrue(retention)
        _logger.info("========= test_12 passed =========")

    def test_13_auto_create_islr_retention_no_journal_raises(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        self.company.write({"islr_supplier_retention_journal_id": False})
        with self.assertRaises(UserError):
            inv.auto_create_islr_retention()
        _logger.info("========= test_13 passed =========")

    def test_14_validate_islr_draft_retention_exists(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        draft_ret = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "payment_concept_id": self.concept_one.id,
                "invoice_type": "in_invoice", "name": "Test",
                "invoice_amount": 500.0, "invoice_total": 500.0,
                "retention_amount": 15.0, "state": "draft",
            })],
        })
        result = inv.validate_islr()
        self.assertIn(draft_ret, result)
        _logger.info("========= test_14 passed =========")

    def test_15_validate_islr_not_posted_raises(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        with self.assertRaises(UserError):
            inv.validate_islr()
        _logger.info("========= test_15 passed =========")

    def test_16_validate_islr_no_payment_concept_raises(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        with self.assertRaises(UserError):
            inv.validate_islr()
        _logger.info("========= test_16 passed =========")

    def test_17_validate_islr_emitted_retention_raises(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        emitted_ret = self.env["account.retention"].create({
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
        emitted_ret.action_post()
        with self.assertRaises(UserError):
            inv.validate_islr()
        _logger.info("========= test_17 passed =========")

    def test_18_validate_municipal_retention_ok(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        self.company.write({"municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id})
        try:
            inv._validate_municipal_retention()
        except UserError:
            self.fail("_validate_municipal_retention raised unexpectedly")
        _logger.info("========= test_18 passed =========")
