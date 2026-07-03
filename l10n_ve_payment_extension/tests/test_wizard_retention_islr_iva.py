from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_batch_retentions_expanded")
class TestWizardBatchRetentionsExpanded(RetentionTestCommon):

    def _create_valid_invoice(self, amount=500):
        inv = self._create_invoice_islr(
            amount, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        return inv

    def _make_batch_line(self, invoice):
        return self.env["batch.retentions.wizard.lines"].create({
            "move_id": invoice.id,
        })

    def test_01_create_muti_retencion_individual(self):
        inv = self._create_valid_invoice()
        line = self._make_batch_line(inv)
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line.id))],
        })
        self.assertTrue(wizard.valid_line_ids)
        result = wizard.create_muti_retencion()
        self.assertIn("domain", result)
        self.assertIn("res_model", result)
        self.assertEqual(result["res_model"], "account.retention")
        _logger.info("========= test_01 passed =========")

    def test_02_create_muti_retencion_grouped(self):
        inv1 = self._create_valid_invoice(500)
        inv2 = self._create_valid_invoice(300)
        line1 = self._make_batch_line(inv1)
        line2 = self._make_batch_line(inv2)
        line1.post_retention = False
        line2.post_retention = False
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "group_retentions": True,
            "line_ids": [(Command.link(line1.id)), (Command.link(line2.id))],
        })
        self.assertTrue(wizard.valid_line_ids)
        result = wizard.create_muti_retencion()
        self.assertIn("domain", result)
        retention_ids = result["domain"][0][2]
        self.assertEqual(len(retention_ids), 1)
        _logger.info("========= test_02 passed =========")

    def test_03_create_muti_retencion_individual_with_post(self):
        inv = self._create_valid_invoice()
        line = self._make_batch_line(inv)
        line.post_retention = True
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line.id))],
        })
        result = wizard.create_muti_retencion()
        self.assertIn("domain", result)
        retention = self.env["account.retention"].browse(result["domain"][0][2])
        self.assertTrue(retention)
        model = self.env["batch.retentions.wizard.lines"]
        self.assertTrue(any(model.browse(result["domain"][0][2])))
        _logger.info("========= test_03 passed =========")

    def test_04_compute_split_lines(self):
        inv = self._create_valid_invoice()
        line = self._make_batch_line(inv)
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line.id))],
        })
        wizard._compute_split_lines()
        self.assertTrue(wizard.valid_line_ids)
        self.assertFalse(wizard.invalid_line_ids)
        _logger.info("========= test_04 passed =========")

    def test_05_compute_split_lines_invalid(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        line = self._make_batch_line(inv)
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line.id))],
        })
        wizard._compute_split_lines()
        self.assertFalse(wizard.valid_line_ids)
        self.assertTrue(wizard.invalid_line_ids)
        _logger.info("========= test_05 passed =========")

    def test_06_compute_values_with_paid(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        inv.write({"payment_state": "paid"})
        line = self._make_batch_line(inv)
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line.id))],
        })
        self.assertTrue(wizard.has_payed_invoices)
        _logger.info("========= test_06 passed =========")

    def test_07_compute_values_with_draft(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        line = self._make_batch_line(inv)
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line.id))],
        })
        self.assertTrue(wizard.has_draft_cancel_invoices)
        _logger.info("========= test_07 passed =========")

    def test_08_create_muti_retencion_no_grouped(self):
        inv1 = self._create_valid_invoice(500)
        inv2 = self._create_valid_invoice(300)
        line1 = self._make_batch_line(inv1)
        line2 = self._make_batch_line(inv2)
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(line1.id)), (Command.link(line2.id))],
        })
        result = wizard.create_muti_retencion()
        self.assertIn("domain", result)
        retention_ids = result["domain"][0][2]
        self.assertEqual(len(retention_ids), 2)
        _logger.info("========= test_08 passed =========")
