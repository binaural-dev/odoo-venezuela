from odoo.tests import tagged, Form
from odoo import Command, fields
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_resync")
class TestRetentionResync(RetentionTestCommon):
    """
    Tests for task #83486 (integridad del recálculo de retenciones):
    button_draft()/button_cancel()/action_post() of a VENDOR invoice
    (in_invoice/in_refund) resyncing its non-cancelled retentions, and
    action_recalculate_retentions()/retention_resync_pending detecting a
    stale retention without needing to draft the invoice.
    """

    def _prepare_invoice(self, invoice):
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})

    def _create_prepared_iva_invoice(self, amount=200, partner=None):
        partner = partner or self.partner_pnr_75
        invoice = self._create_invoice_reten_iva(
            amount=amount, partner=partner,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        return invoice

    def _emit_iva_retention(self, invoice):
        """
        Generates and emits an IVA retention for `invoice` through the real
        action_post() flow (generate_iva_retention), so the retention lines
        are built by compute_retention_lines_data() exactly like production
        data, instead of being hand-crafted.
        """
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = invoice.retention_iva_line_ids.mapped("retention_id").filtered(
            lambda r: r.state != "cancel"
        )
        self.assertEqual(retention.state, "emitted")
        return retention

    def _create_emitted_municipal_retention(self, invoice, retention_amount=10.0):
        self.company.write({
            "municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
        })
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": invoice.partner_id.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "Muni Line",
                "invoice_total": invoice.amount_total, "invoice_amount": invoice.amount_untaxed,
                "retention_amount": retention_amount, "foreign_invoice_amount": invoice.amount_untaxed,
                "foreign_retention_amount": retention_amount,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        return retention

    # 1. button_draft() of the invoice leaves the retention/payment in draft,
    # intact (no orphans), without clearing the voucher number.
    def test_01_button_draft_drafts_retention_without_orphaning(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids
        voucher_number = invoice.iva_voucher_number
        self.assertTrue(voucher_number)

        invoice.button_draft()

        self.assertEqual(invoice.state, "draft")
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.payment_ids, payment)
        self.assertEqual(payment.state, "draft")
        self.assertEqual(invoice.iva_voucher_number, voucher_number)
        _logger.info("========= test_01 passed =========")

    # 2. Repost without any real change brings the retention back to
    # 'emitted' reusing the SAME payment and amount.
    def test_02_repost_without_changes_resyncs_same_payment(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids
        original_amount = payment.amount

        invoice.button_draft()
        invoice.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.payment_ids, payment)
        self.assertAlmostEqual(payment.amount, original_amount, places=2)
        _logger.info("========= test_02 passed =========")

    # 3. Repost after editing the base rebuilds the retention lines/amount
    # against the new base, reusing (not orphaning) the same payment.
    def test_03_repost_with_edited_base_rebuilds_amount(self):
        invoice = self._create_prepared_iva_invoice(amount=200)
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids

        invoice.button_draft()
        with Form(invoice) as inv_form:
            with inv_form.invoice_line_ids.edit(0) as line:
                line.price_unit = 300.0
        invoice = inv_form.save()
        invoice.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertEqual(len(retention.payment_ids), 1)
        self.assertEqual(retention.payment_ids, payment)

        lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertAlmostEqual(sum(lines_of_move.mapped("invoice_amount")), 300.0, places=2)
        expected_amount = sum(lines_of_move.mapped("retention_amount"))
        self.assertAlmostEqual(payment.amount, expected_amount, places=2)
        _logger.info("========= test_03 passed =========")

    # 4. Repost when the invoice no longer carries a taxed line cancels the
    # retention instead of blocking the invoice's repost.
    def test_04_repost_without_tax_cancels_retention(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)

        invoice.button_draft()
        invoice.invoice_line_ids.write({"tax_ids": [Command.set([self.tax_iva_exent_purchase.id])]})
        invoice.action_post()

        self.assertEqual(invoice.state, "posted")
        self.assertEqual(retention.state, "cancel")
        _logger.info("========= test_04 passed =========")

    # 5. button_draft() is blocked, with no side effects, when the
    # retention groups several invoices.
    def test_05_button_draft_blocked_for_grouped_retention(self):
        invoice_1 = self._create_prepared_iva_invoice(amount=200)
        invoice_2 = self._create_prepared_iva_invoice(amount=150)
        invoice_1.action_post()
        invoice_2.action_post()

        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice_1.id, "name": "IVA Line 1",
                    "invoice_total": 232.0, "invoice_amount": 200.0,
                    "retention_amount": 24.0, "foreign_invoice_amount": 200.0,
                    "foreign_retention_amount": 24.0, "foreign_currency_rate": 1.0,
                }),
                Command.create({
                    "move_id": invoice_2.id, "name": "IVA Line 2",
                    "invoice_total": 174.0, "invoice_amount": 150.0,
                    "retention_amount": 18.0, "foreign_invoice_amount": 150.0,
                    "foreign_retention_amount": 18.0, "foreign_currency_rate": 1.0,
                }),
            ],
        })
        retention.number = "01234567891234"
        retention.action_post()

        with self.assertRaises(UserError):
            invoice_1.button_draft()

        self.assertEqual(invoice_1.state, "posted")
        self.assertEqual(retention.state, "emitted")
        _logger.info("========= test_05 passed =========")

    # 6. _check_retention_paid_lock(): button_draft() and
    # action_recalculate_retentions() refuse to touch an invoice with a
    # REAL payment applied (not just the retention's own payment - see
    # test_06b for that case, which must NOT block).
    def test_06_paid_lock_blocks_draft_and_recalculate(self):
        invoice = self._create_prepared_iva_invoice()
        self._emit_iva_retention(invoice)

        wizard = self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create({
            "amount": invoice.amount_residual,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        })
        wizard.action_create_payments()

        with self.assertRaises(UserError):
            invoice.button_draft()

        with self.assertRaises(UserError):
            invoice.action_recalculate_retentions()
        _logger.info("========= test_06 passed =========")

    # 6b. A retention's own payment being the only thing reconciled
    # against the invoice must NOT block button_draft()/
    # action_recalculate_retentions() - only a REAL external payment does.
    def test_06b_retention_only_payment_does_not_block(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids

        self.assertTrue(payment.is_retention)
        invoice._check_retention_paid_lock()  # must not raise

        invoice.button_draft()
        self.assertEqual(retention.state, "draft")
        _logger.info("========= test_06b passed =========")

    # 7. button_cancel() of the invoice cancels its emitted retention(s)
    # before the invoice itself is cancelled.
    def test_07_button_cancel_cancels_retention(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)

        invoice.button_cancel()

        self.assertEqual(retention.state, "cancel")
        self.assertEqual(invoice.state, "cancel")
        _logger.info("========= test_07 passed =========")

    # 8. action_cancel() of a retention whose payment was already drafted
    # by a previous resync (button_draft()) no longer fails.
    def test_08_action_cancel_after_resync_draft(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)

        invoice.button_draft()
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.payment_ids.state, "draft")

        retention.action_cancel()

        self.assertEqual(retention.state, "cancel")
        _logger.info("========= test_08 passed =========")

    # 9. retention_resync_pending / _get_retentions_pending_resync(): False when
    # everything matches, True when the declared base (IVA) or the linked
    # payment's amount (also covers Municipal) no longer match what the
    # generators would recompute - and turns False again after
    # action_recalculate_retentions().
    def test_09_resync_pending_detects_diff_and_clears(self):
        invoice = self._create_prepared_iva_invoice(amount=200)
        retention = self._emit_iva_retention(invoice)
        self.assertFalse(invoice.retention_resync_pending)
        self.assertFalse(retention.retention_resync_pending)

        # Desync the declared base directly on the retention line, without
        # touching the (locked/posted) invoice itself.
        lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        lines_of_move[:1].write({"invoice_amount": lines_of_move[0].invoice_amount + 50.0})

        invoice.invalidate_recordset(["retention_resync_pending"])
        retention.invalidate_recordset(["retention_resync_pending"])
        self.assertTrue(invoice.retention_resync_pending)
        self.assertTrue(retention.retention_resync_pending)

        self.assertIn(retention, invoice._get_retentions_pending_resync())

        invoice.action_recalculate_retentions()

        invoice.invalidate_recordset(["retention_resync_pending"])
        retention.invalidate_recordset(["retention_resync_pending"])
        self.assertFalse(invoice.retention_resync_pending)
        self.assertFalse(retention.retention_resync_pending)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(retention.state, "emitted")
        _logger.info("========= test_09 passed =========")

    def test_09b_resync_pending_detects_payment_amount_mismatch_municipal(self):
        invoice = self._create_prepared_iva_invoice(amount=200)
        invoice.action_post()
        retention = self._create_emitted_municipal_retention(invoice, retention_amount=10.0)
        payment = retention.payment_ids

        self.assertFalse(invoice.retention_resync_pending)

        payment.write({"amount": payment.amount + 5.0})

        invoice.invalidate_recordset(["retention_resync_pending"])
        self.assertTrue(invoice.retention_resync_pending)
        _logger.info("========= test_09b passed =========")

    # 10. retention_resync_pending/payment.retention_resync_pending
    # propagate the invoice's diff; a non-retention payment never reports
    # True.
    def test_10_resync_pending_propagates_to_payment(self):
        invoice = self._create_prepared_iva_invoice(amount=200)
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids

        lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        lines_of_move[:1].write({"invoice_amount": lines_of_move[0].invoice_amount + 50.0})

        payment.invalidate_recordset(["retention_resync_pending"])
        self.assertTrue(payment.retention_resync_pending)

        # A payment that is not a retention never reports pending, even
        # after the recordset is refreshed.
        other_payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_pnr_75.id,
            "amount": 10.0,
            "journal_id": self.bank_journal_sub.id,
            "is_retention": False,
        })
        self.assertFalse(other_payment.retention_resync_pending)
        _logger.info("========= test_10 passed =========")

    # 11. action_recalculate_retentions() end-to-end: the invoice stays
    # 'posted' the whole time, nothing is drafted, and the retention ends
    # up consistent again.
    def test_11_action_recalculate_retentions_keeps_invoice_posted(self):
        invoice = self._create_prepared_iva_invoice(amount=200)
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids

        lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        lines_of_move[:1].write({"invoice_amount": lines_of_move[0].invoice_amount + 50.0})

        self.assertEqual(invoice.state, "posted")
        invoice.action_recalculate_retentions()
        self.assertEqual(invoice.state, "posted")

        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.payment_ids, payment)
        lines_of_move = retention.retention_line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertAlmostEqual(sum(lines_of_move.mapped("invoice_amount")), 200.0, places=2)
        _logger.info("========= test_11 passed =========")

    # action_recalculate_retentions() is a no-op (and does not raise) when
    # there is nothing to resync.
    def test_12_action_recalculate_retentions_noop_when_in_sync(self):
        invoice = self._create_prepared_iva_invoice()
        retention = self._emit_iva_retention(invoice)
        payment = retention.payment_ids

        invoice.action_recalculate_retentions()

        self.assertEqual(invoice.state, "posted")
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.payment_ids, payment)
        _logger.info("========= test_12 passed =========")
