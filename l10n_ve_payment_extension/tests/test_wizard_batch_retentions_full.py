from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_batch_retentions")
class TestWizardBatchRetentions(RetentionTestCommon):

    def test_01_compute_name(self):
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
        })
        self.assertIn("ISLR", wizard.name)
        _logger.info("========= test_01 passed =========")

    def test_02_compute_split_lines_empty(self):
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
        })
        self.assertFalse(wizard.valid_line_ids)
        _logger.info("========= test_02 passed =========")

    def test_03_compute_values_no_lines(self):
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
        })
        self.assertFalse(wizard.has_payed_invoices)
        self.assertFalse(wizard.has_draft_cancel_invoices)
        _logger.info("========= test_03 passed =========")

    def test_04_create_muti_retencion_no_lines_raises(self):
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
        })
        with self.assertRaises(UserError):
            wizard.create_muti_retencion()
        _logger.info("========= test_04 passed =========")

    def test_05_compute_values_with_valid_line(self):
        invoice = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        batch_line = self.env["batch.retentions.wizard.lines"].create({
            "move_id": invoice.id,
        })
        wizard = self.env["batch.retentions.wizard"].create({
            "type_retention": "islr",
            "line_ids": [(Command.link(batch_line.id))],
        })
        _logger.info("========= test_05 passed =========")
