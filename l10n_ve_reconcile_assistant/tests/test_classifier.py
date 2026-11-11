from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from .common import ReconcileAssistantCommon


@tagged("l10n_ve_reconcile_assistant", "-at_install", "post_install")
class TestClassifier(ReconcileAssistantCommon):
    """El clasificador decide si la selección la maneja el asistente, si se puede conciliar y por qué se
    bloquea: los 2 casos permitidos y las combinaciones que romperían el vínculo con el pago origen."""

    def _classify(self, *lines):
        return sum(lines, self.env["account.move.line"])._l10n_ve_reconcile_classify()

    def _assert_blocked(self, result, fragment):
        self.assertTrue(result["handled"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["case"])
        self.assertTrue(
            any(fragment in reason for reason in result["reasons"]),
            f"Se esperaba un motivo con «{fragment}»: {result['reasons']}",
        )

    def test_payment_against_invoice_is_allowed(self):
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-08-01")
        result = self._classify(self._receivable_line(invoice), payment)
        self.assertTrue(result["handled"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["case"], "payment")
        self.assertEqual(result["origins"], payment)
        self.assertEqual(result["invoices"], self._receivable_line(invoice))
        self.assertFalse(result["reasons"])

    def test_advance_against_two_invoices_is_allowed(self):
        invoices = self._invoice("2026-08-01", 100.0, self.usd) + self._invoice("2026-08-01", 80.0, self.usd)
        advance = self._advance_payment(self.bank["USD"], 170.0)
        result = self._classify(*[self._receivable_line(invoice) for invoice in invoices], advance)
        self.assertTrue(result["ok"])
        self.assertEqual(result["case"], "advance")
        self.assertEqual(result["origins"], advance)

    def test_selections_without_invoice_and_origin_stay_native(self):
        """Dos pagos sin factura, o dos facturas sin pago: no es de este asistente."""
        first = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        second = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        self.assertFalse(self._classify(first, second)["handled"])
        invoices = self._invoice("2026-08-01", 100.0) + self._invoice("2026-08-01", 50.0)
        result = self._classify(*[self._receivable_line(invoice) for invoice in invoices])
        self.assertFalse(result["handled"])
        self.assertFalse(result["ok"])

    def test_cross_entry_line_is_blocked(self):
        invoice = self._invoice("2026-08-01", 100.0)
        # Sin publicar: un cruce sin pago origen no se puede publicar; basta para clasificarlo.
        cross = self._entry_line(self.acc_receivable, 0.0, 50.0, is_advance_move=True, post=False)
        self._assert_blocked(self._classify(self._receivable_line(invoice), cross), "advance cross entry")

    def test_exchange_or_igtf_note_line_is_blocked(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        with patch.object(self.env.registry["account.move"], "_l10n_ve_reconcile_is_special_note",
                          return_value=True):
            result = self._classify(self._receivable_line(invoice), payment)
        self._assert_blocked(result, "debit/credit note")

    def test_advance_without_invoice_is_blocked(self):
        advance = self._advance_payment(self.bank["USD"], 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        self._assert_blocked(self._classify(advance, payment), "against an invoice")

    def test_advance_against_another_account_is_blocked(self):
        advance = self._advance_payment(self.bank["USD"], 100.0)
        expense = self._entry_line(self.env["account.account"].search(
            [("account_type", "=", "expense")], limit=1), 100.0, 0.0)
        self._assert_blocked(self._classify(advance, expense), "not against another account")

    def test_several_payments_against_one_invoice_are_blocked(self):
        """Con más de un origen el resultado dependería del orden: cada pago se concilia por separado."""
        invoice = self._invoice("2026-08-01", 100.0)
        first = self._outstanding_line(self.bank["VEF"], 60.0, self.vef, "2026-08-01")
        second = self._outstanding_line(self.bank["VEF"], 40.0, self.vef, "2026-08-01")
        result = self._classify(self._receivable_line(invoice), first, second)
        self._assert_blocked(result, "single payment or advance")
        self.assertEqual(result["origins"], first + second)

    def test_a_payment_and_an_advance_together_are_blocked(self):
        invoice = self._invoice("2026-08-01", 150.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-08-01")
        advance = self._advance_payment(self.bank["USD"], 60.0)
        self._assert_blocked(self._classify(self._receivable_line(invoice), payment, advance),
                             "single payment or advance")

    def test_one_payment_against_many_invoices_has_no_limit(self):
        invoices = [self._invoice("2026-08-01", 10.0) for _i in range(5)]
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        result = self._classify(*[self._receivable_line(invoice) for invoice in invoices], payment)
        self.assertTrue(result["ok"])
        self.assertEqual(result["case"], "payment")
        self.assertEqual(len(result["invoices"]), 5)

    def test_several_origins_against_several_invoices_are_blocked(self):
        invoices = self._invoice("2026-08-01", 100.0) + self._invoice("2026-08-01", 80.0)
        first = self._outstanding_line(self.bank["VEF"], 60.0, self.vef, "2026-08-01")
        second = self._outstanding_line(self.bank["VEF"], 40.0, self.vef, "2026-08-01")
        result = self._classify(*[self._receivable_line(invoice) for invoice in invoices], first, second)
        self._assert_blocked(result, "single payment or advance")

    def test_advance_account_lines_are_told_apart_by_side_and_origin(self):
        """`is_advance_move` marca tanto el cruce como el residual de un pago hecho de más: se decide por
        la línea. Sin pago de origen, el lado del anticipo es `other` y el que consume es `cross`."""
        credit = self._entry_line(self.advance_account, 0.0, 50.0, post=False)
        debit = self._entry_line(self.advance_account, 50.0, 0.0, is_advance_move=True, post=False)
        self.assertEqual(credit._l10n_ve_reconcile_kind(), "other")
        self.assertEqual(debit._l10n_ve_reconcile_kind(), "cross")

    def test_open_amount_is_always_positive(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 40.0, self.vef, "2026-08-01")
        self.assertAlmostEqual(self._receivable_line(invoice).l10n_ve_open_amount, 100.0, places=2)
        self.assertAlmostEqual(payment.l10n_ve_open_amount, 40.0, places=2)

    def test_different_partners_are_blocked(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        other = self._entry_line(self.acc_receivable, 10.0, 0.0, partner=self.other_partner)
        self._assert_blocked(self._classify(self._receivable_line(invoice), payment, other), "different partners")

    def test_different_companies_are_blocked(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        other_company = self.env["res.company"].create({"name": "Otra compañía Prueba Asistente"})
        company_ids = [Command.set([other_company.id])]
        receivable = self.env["account.account"].create({
            "name": "CxC otra compañía", "code": "1101OTH", "account_type": "asset_receivable",
            "reconcile": True, "company_ids": company_ids})
        income = self.env["account.account"].create({
            "name": "Ingresos otra compañía", "code": "4001OTH", "account_type": "income",
            "company_ids": company_ids})
        journal = self.env["account.journal"].create({
            "name": "Diario otra compañía", "type": "general", "code": "OTHJ", "company_id": other_company.id})
        entry = self.env["account.move"].with_company(other_company).create({
            "move_type": "entry", "journal_id": journal.id, "date": "2026-08-01",
            "line_ids": [
                Command.create({"account_id": receivable.id, "debit": 10.0, "partner_id": self.partner.id}),
                Command.create({"account_id": income.id, "credit": 10.0, "partner_id": self.partner.id}),
            ],
        })
        entry.action_post()
        other = entry.line_ids.filtered(lambda line: line.account_id == receivable)
        self._assert_blocked(self._classify(self._receivable_line(invoice), payment, other), "different companies")

    def test_unposted_or_reconciled_lines_are_blocked(self):
        invoice = self._invoice("2026-08-01", 100.0)
        draft = self._outstanding_line(self.bank["VEF"], 50.0, self.vef, "2026-08-01")
        draft.payment_id.action_draft()
        self.assertEqual(draft.parent_state, "draft")
        self._assert_blocked(self._classify(self._receivable_line(invoice), draft), "posted and not reconciled")
        paid = self._invoice("2026-08-01", 40.0)
        payment = self._outstanding_line(self.bank["VEF"], 40.0, self.vef, "2026-08-01")
        paid.js_assign_outstanding_line(payment.id)
        again = self._outstanding_line(self.bank["VEF"], 10.0, self.vef, "2026-08-01")
        self._assert_blocked(self._classify(self._receivable_line(paid), again), "posted and not reconciled")

    def test_payment_in_the_wrong_direction_is_blocked(self):
        """Un pago recibido contra una factura de proveedor: ambos son créditos."""
        bill = self._invoice("2026-08-01", 100.0, move_type="in_invoice")
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        bill_line = bill.line_ids.filtered(lambda line: line.account_type == "liability_payable")
        self.assertEqual(self._classify(bill_line, payment)["handled"], True)
        self._assert_blocked(self._classify(bill_line, payment), "opposite directions")

    def test_extra_blockers_hook_adds_reasons(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        with patch.object(self.env.registry["account.move.line"], "_l10n_ve_reconcile_extra_blockers",
                          return_value=["Motivo de otro módulo"]):
            result = self._classify(self._receivable_line(invoice), payment)
        self._assert_blocked(result, "Motivo de otro módulo")

    def test_special_note_hook_and_apply_context_defaults(self):
        invoice = self._invoice("2026-08-01", 100.0)
        self.assertFalse(invoice._l10n_ve_reconcile_is_special_note())
        self.assertEqual(invoice._l10n_ve_reconcile_apply_context(), {})
        self.assertEqual(self._receivable_line(invoice)._l10n_ve_reconcile_extra_blockers(), [])
