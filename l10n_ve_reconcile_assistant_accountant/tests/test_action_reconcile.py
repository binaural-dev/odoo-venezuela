from odoo.tests import tagged

from odoo.addons.l10n_ve_reconcile_assistant.tests.common import ReconcileAssistantCommon


@tagged("l10n_ve_reconcile_assistant", "-at_install", "post_install")
class TestActionReconcile(ReconcileAssistantCommon):
    """El botón Reconciliar de la conciliación manual: abre el asistente en lo que maneja y deja pasar
    a la conciliación nativa el resto."""

    def test_payment_against_invoice_opens_the_assistant(self):
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-08-01")
        lines = self._receivable_line(invoice) + payment
        action = lines.action_reconcile()
        self.assertEqual(action["res_model"], "l10n_ve.reconcile.assistant")
        self.assertEqual(action["context"]["active_ids"], lines.ids)
        self.assertEqual(invoice.payment_state, "not_paid", "Abrir el asistente no concilia nada")
        wizard = self._open_assistant(lines)
        wizard.action_confirm()
        self.assertEqual(invoice.payment_state, "paid")

    def test_blocked_combination_also_opens_the_assistant(self):
        advance = self._advance_payment(self.bank["USD"], 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        action = (advance + payment).action_reconcile()
        self.assertEqual(action["res_model"], "l10n_ve.reconcile.assistant")

    def test_other_selections_follow_the_native_reconciliation(self):
        debit = self._entry_line(self.acc_receivable, 100.0, 0.0)
        credit = self._entry_line(self.acc_receivable, 0.0, 100.0)
        (debit + credit).action_reconcile()
        self.assertTrue(debit.reconciled)
        self.assertTrue(credit.reconciled)

    def test_empty_selection_does_nothing(self):
        self.assertFalse(self.env["account.move.line"].action_reconcile())
