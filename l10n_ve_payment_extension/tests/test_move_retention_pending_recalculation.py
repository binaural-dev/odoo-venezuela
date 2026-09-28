from odoo.tests import tagged
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "move_retention_pending_recalculation")
class TestMoveRetentionPendingRecalculation(RetentionTestCommon):
    """
    Task #83486: the "stale retention" banner must only appear when the
    invoice lines were modified AFTER the emitted IVA/ISLR retention was
    generated, not simply because the invoice is draft and has an emitted
    retention.
    """

    def _create_draft_invoice_with_emitted_iva_retention(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.generate_iva_retention = True
        invoice.action_post()

        retention = invoice.retention_iva_line_ids.retention_id
        self.assertTrue(retention)
        if retention.state != "emitted":
            retention.action_post()
        self.assertEqual(retention.state, "emitted")

        invoice.with_context(bypass_retention_lock=True).button_draft()
        self.assertEqual(invoice.state, "draft")
        return invoice, retention

    def test_01_no_banner_when_lines_not_edited_after_emission(self):
        invoice, _retention = self._create_draft_invoice_with_emitted_iva_retention()
        self.assertFalse(
            invoice.has_pending_retention_recalculation,
            "The banner should not appear when the invoice lines were not "
            "modified after the retention was emitted.",
        )
        _logger.info("========= test_01 passed =========")

    def test_02_banner_when_lines_edited_after_emission(self):
        invoice, retention = self._create_draft_invoice_with_emitted_iva_retention()
        invoice.invoice_line_ids[0].write({"price_unit": 999.0})
        self.assertGreater(
            invoice.invoice_line_ids[0].write_date, retention.write_date
        )
        self.assertTrue(
            invoice.has_pending_retention_recalculation,
            "The banner should appear when the invoice lines were modified "
            "after the retention was emitted.",
        )
        _logger.info("========= test_02 passed =========")
