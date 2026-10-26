from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import ExchangeNoteCommon


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteForeignAndDraft(ExchangeNoteCommon):
    """Las ND/NC por diferencial cambiario trabajan como el asiento de
    diferencial nativo: sin montos en moneda alterna y sin poder volver a
    borrador. Reutiliza el fixture compartido `ExchangeNoteCommon`
    (`common.py`)."""

    def _settle_and_get_note(self):
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        pay_form.record.action_create_payments()
        self.env.cr.flush()
        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(note), 1, "Setup sanity: debió crearse la ND/NC.")
        return invoice, note

    def test_note_lines_have_zero_foreign_amounts(self):
        invoice, note = self._settle_and_get_note()
        self.assertTrue(
            any(invoice.line_ids.mapped(lambda l: l.foreign_debit or l.foreign_credit)),
            "Control: la factura sí lleva montos en moneda alterna.",
        )
        for line in note.line_ids:
            self.assertEqual(line.foreign_debit, 0.0)
            self.assertEqual(line.foreign_credit, 0.0)
            self.assertEqual(line.foreign_balance, 0.0)

    def test_note_foreign_amounts_stay_zero_after_recompute(self):
        _invoice, note = self._settle_and_get_note()
        note.line_ids._compute_foreign_debit_credit()
        note.line_ids.invalidate_recordset()
        self.assertFalse(note.line_ids.filtered(lambda l: l.foreign_debit or l.foreign_credit))

    def test_note_cannot_be_reset_to_draft(self):
        _invoice, note = self._settle_and_get_note()
        with self.assertRaises(UserError):
            note.button_draft()
        self.assertEqual(note.state, "posted")

    def test_reversal_of_note_cannot_be_reset_to_draft(self):
        invoice, note = self._settle_and_get_note()
        payment_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (invoice_line + payment_line.matched_debit_ids.debit_move_id
         + payment_line.matched_credit_ids.credit_move_id).remove_move_reconcile()
        note.invalidate_recordset()
        reversal = note.reversal_move_ids
        self.assertTrue(reversal, "Setup sanity: la nota debió revertirse.")
        with self.assertRaises(UserError):
            reversal.button_draft()

    def test_regular_invoice_can_still_be_reset_to_draft(self):
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        invoice.button_draft()
        self.assertEqual(invoice.state, "draft")
