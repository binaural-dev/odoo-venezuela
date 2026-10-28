from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common_currency import CurrencyFixtureCommon


@tagged("l10n_ve_igtf", "-at_install", "post_install")
class TestUnreconcileAdvanceCross(CurrencyFixtureCommon):
    """Al desconciliar, el asiento ORIGEN del pago nunca se cancela: solo el asiento de CRUCE de anticipo,
    y solo si es su parcial el que se rompe. La rama que lo cancela se activa si `payment.advanced_move_ids`
    no está vacío, y ese campo solo debe traer cruces publicados (con `domain` como cadena traía los de borrador).
    Casos: cruce sin publicar ligado al pago, cruce publicado, y parcial del propio asiento de cruce."""

    def setUp(self):
        super().setUp()
        self.misc_journal = self.env["account.journal"].search(
            [("code", "=", "EXCHW"), ("company_id", "=", self.company.id)], limit=1,
        )
        self.advance_account = self.env["account.account"].create({
            "name": "Anticipo (prueba cruce)", "code": "2301ADV",
            "account_type": "liability_current", "company_ids": [Command.set([self.company.id])],
        })

    def _cross_entry(self, payment, post, advance=False):
        """Asiento de cruce de anticipo ligado a `payment` (100 Bs: CxC cliente
        contra la cuenta de anticipo), publicado o en borrador. `advance` lo marca `is_advance_move`,
        como los cruces reales."""
        entry = self.env["account.move"].create({
            "is_advance_move": advance,
            "move_type": "entry",
            "journal_id": self.misc_journal.id,
            "date": "2026-08-01",
            "origin_payment_advanced_payment_id": payment.id,
            "line_ids": [
                Command.create({"account_id": self.advance_account.id, "debit": 100.0, "credit": 0.0,
                                "partner_id": self.partner.id}),
                Command.create({"account_id": self.acc_receivable.id, "debit": 0.0, "credit": 100.0,
                                "partner_id": self.partner.id}),
            ],
        })
        if post:
            entry.action_post()
        return entry

    def _paid_invoice_with_payment(self):
        """Factura en VEF de 100 saldada con un pago en VEF (parcial entre la
        factura y el asiento PROPIO del pago)."""
        invoice = self._invoice("2026-08-01", 100.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        invoice.js_assign_outstanding_line(payment_line.id)
        self.assertEqual(invoice.payment_state, "paid")
        payment = payment_line.move_id.origin_payment_id
        partial = (payment_line.matched_debit_ids | payment_line.matched_credit_ids)
        self.assertEqual(len(partial), 1)
        return invoice, payment, payment_line, partial

    def test_unposted_cross_entry_never_cancels_the_origin_payment(self):
        """Pago con un cruce sin publicar ligado y se desconcilia el parcial del propio pago: el asiento
        origen no debe cancelarse; es un desconciliado normal. `advanced_move_ids` solo trae cruces publicados,
        por eso el cruce en borrador no activa la rama que cancela cruces."""
        invoice, payment, payment_line, partial = self._paid_invoice_with_payment()
        draft_cross = self._cross_entry(payment, post=False)
        payment.invalidate_recordset()
        self.assertEqual(draft_cross.state, "draft")
        self.assertNotIn(draft_cross, payment.advanced_move_ids)

        invoice.js_remove_outstanding_partial(partial.id)

        self.assertEqual(payment.move_id.state, "posted", "El asiento origen del pago no debe cancelarse")
        self.assertFalse(partial.exists(), "El parcial debía desconciliarse")
        self.assertEqual(invoice.payment_state, "not_paid")

    def test_posted_cross_entry_asks_for_confirmation_and_cancels_nothing(self):
        """Pago con un cruce PUBLICADO: desconciliar el parcial del propio pago abre
        el wizard de confirmación y no cancela ni desconcilia nada todavía."""
        invoice, payment, payment_line, partial = self._paid_invoice_with_payment()
        self._cross_entry(payment, post=True)
        payment.invalidate_recordset()
        self.assertTrue(payment.advanced_move_ids)

        action = invoice.js_remove_outstanding_partial(partial.id)

        self.assertIsInstance(action, dict)
        self.assertEqual(action.get("res_model"), "move.action.cancel.advance.payment.wizard")
        self.assertEqual(payment.move_id.state, "posted")
        self.assertTrue(partial.exists(), "No se desconcilia hasta confirmar en el wizard")

    def test_breaking_the_cross_entry_partial_cancels_only_the_cross_entry(self):
        """Desconciliar la factura del asiento de CRUCE cancela ese cruce y deja el
        pago intacto (publicado)."""
        invoice = self._invoice("2026-08-01", 100.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self._cross_entry(payment, post=True)
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (invoice_line + cross_line).reconcile()
        self.assertEqual(invoice.payment_state, "paid")
        partial = cross_line.matched_debit_ids | cross_line.matched_credit_ids

        invoice.js_remove_outstanding_partial(partial.id)

        self.assertEqual(cross.state, "cancel", "El asiento de cruce debía cancelarse")
        self.assertEqual(payment.move_id.state, "posted", "El pago origen no debe cancelarse")
        self.assertFalse(partial.exists())
        self.assertEqual(invoice.payment_state, "not_paid")

    def test_cross_entry_cannot_be_reset_to_draft_or_cancelled_by_its_own_buttons(self):
        """Los botones propios del cruce no lo deshacen: solo la desconciliación desde la factura o el pago origen."""
        invoice, payment, payment_line, partial = self._paid_invoice_with_payment()
        cross = self._cross_entry(payment, post=True, advance=True)
        with self.assertRaises(UserError):
            cross.button_draft()
        with self.assertRaises(UserError):
            cross.button_cancel()
        self.assertEqual(cross.state, "posted")

    def test_cancelled_cross_entry_cannot_be_reposted_without_origin_payment(self):
        """Al desconciliar desde la factura el cruce se cancela y se desliga del pago; ya no puede volver a
        borrador ni publicarse sin pago origen (`is_advance_move` sobrevive a la cancelación)."""
        invoice = self._invoice("2026-08-01", 100.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self._cross_entry(payment, post=True, advance=True)
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (invoice_line + cross_line).reconcile()
        partial = cross_line.matched_debit_ids | cross_line.matched_credit_ids

        invoice.js_remove_outstanding_partial(partial.id)

        self.assertEqual(cross.state, "cancel")
        self.assertFalse(cross.origin_payment_advanced_payment_id)
        self.assertTrue(cross.is_advance_move)
        with self.assertRaises(UserError):
            cross.button_draft()

    def test_cross_entry_without_origin_payment_cannot_be_posted(self):
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self._cross_entry(payment, post=False, advance=True)
        cross.origin_payment_advanced_payment_id = False
        with self.assertRaises(UserError):
            cross.action_post()
        cross.origin_payment_advanced_payment_id = payment
        cross.action_post()
        self.assertEqual(cross.state, "posted")

    def test_cancelling_the_origin_payment_cancels_its_draft_cross_entries(self):
        """Un cruce que quedó en borrador ligado al pago se cancela y se desliga junto con el pago origen."""
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        draft_cross = self._cross_entry(payment, post=False, advance=True)

        payment.action_cancel()

        self.assertEqual(payment.state, "canceled")
        self.assertEqual(draft_cross.state, "cancel")
        self.assertFalse(draft_cross.origin_payment_advanced_payment_id)

    def test_remove_igtf_runs_the_cross_entry_through_its_managed_path(self):
        """`remove_igtf_from_account_move` traga cualquier error de `button_draft`/`button_cancel` y devuelve
        False. Con un cruce marcado debe completar el camino gestionado (devuelve True, cruce cancelado y
        desligado), no fallar en silencio contra la guarda de sus botones."""
        invoice = self._invoice("2026-08-01", 100.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self._cross_entry(payment, post=True, advance=True)
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (invoice_line + cross_line).reconcile()
        partial = cross_line.matched_debit_ids | cross_line.matched_credit_ids

        self.assertTrue(invoice.remove_igtf_from_account_move(partial.id))

        self.assertEqual(cross.state, "cancel")
        self.assertFalse(cross.origin_payment_advanced_payment_id)

    def test_orphan_cross_entry_is_cancelled_when_unreconciled_from_the_invoice(self):
        """Un cruce publicado que perdió su pago origen (pago borrado o dato histórico) ya no tiene función:
        al desconciliarlo desde la factura se cancela, sin quedar atrapado contra la guarda de `_post`."""
        invoice = self._invoice("2026-08-01", 100.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self._cross_entry(payment, post=True, advance=True)
        cross.origin_payment_advanced_payment_id = False
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (invoice_line + cross_line).reconcile()
        partial = cross_line.matched_debit_ids | cross_line.matched_credit_ids

        invoice.js_remove_outstanding_partial(partial.id)

        self.assertEqual(cross.state, "cancel")
        self.assertFalse(partial.exists())
        self.assertEqual(invoice.payment_state, "not_paid")

    def test_cancelling_the_origin_payment_leaves_non_advance_drafts_alone(self):
        """Los asientos en borrador que apuntan al pago por `origin_payment_advanced_payment_id` pero no son
        cruces de anticipo (p. ej. los de las integraciones) no se cancelan."""
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        foreign_draft = self._cross_entry(payment, post=False, advance=False)

        payment.action_cancel()

        self.assertEqual(foreign_draft.state, "draft")
        self.assertEqual(foreign_draft.origin_payment_advanced_payment_id, payment)

    def test_orphan_cross_entry_with_igtf_line_is_cancelled_when_unreconciled(self):
        """Caso del review: cruce publicado, sin pago origen y con línea de IGTF. `remove_igtf_from_account_move`
        lo pasa a borrador (rompe el parcial); antes lo volvía a publicar, la guarda de `_post` lo rechazaba y
        `js_remove_outstanding_partial` terminaba en `MissingError`. Ahora se cancela y la factura se desconcilia."""
        igtf_account = self.env["account.account"].create({
            "name": "IGTF por pagar (prueba cruce)", "code": "2302IGT",
            "account_type": "liability_current", "company_ids": [Command.set([self.company.id])],
        })
        self.company.customer_account_igtf_id = igtf_account
        self.partner.property_account_receivable_id = self.acc_receivable
        self.partner.default_advance_customer_account_id = self.advance_account
        invoice = self._invoice("2026-08-01", 100.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self.env["account.move"].create({
            "is_advance_move": True,
            "move_type": "entry",
            "journal_id": self.misc_journal.id,
            "date": "2026-08-01",
            "origin_payment_advanced_payment_id": payment.id,
            "partner_id": self.partner.id,
            "line_ids": [
                Command.create({"account_id": self.advance_account.id, "debit": 100.0, "credit": 0.0,
                                "partner_id": self.partner.id}),
                Command.create({"account_id": self.acc_receivable.id, "debit": 0.0, "credit": 97.0,
                                "partner_id": self.partner.id}),
                Command.create({"account_id": igtf_account.id, "debit": 0.0, "credit": 3.0,
                                "partner_id": self.partner.id}),
            ],
        })
        cross.action_post()
        cross.origin_payment_advanced_payment_id = False
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (invoice_line + cross_line).reconcile()
        partial = cross_line.matched_debit_ids | cross_line.matched_credit_ids

        invoice.js_remove_outstanding_partial(partial.id)

        self.assertEqual(cross.state, "cancel")
        self.assertFalse(partial.exists())
        self.assertEqual(invoice.payment_state, "not_paid")

    def test_orphan_cross_entry_cancel_also_unreconciles_its_other_invoices(self):
        """Cancelar un cruce implica desconciliar TODAS sus líneas (`button_draft` no distingue parciales): un
        cruce huérfano aplicado a dos facturas las deja a ambas sin pagar, igual que un cruce con pago origen,
        y no deja ningún parcial colgando del asiento cancelado."""
        invoice_1 = self._invoice("2026-08-01", 50.0)
        invoice_2 = self._invoice("2026-08-01", 50.0)
        payment_line = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        payment = payment_line.move_id.origin_payment_id
        cross = self._cross_entry(payment, post=True, advance=True)
        cross.origin_payment_advanced_payment_id = False
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        for invoice in (invoice_1, invoice_2):
            invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            (invoice_line + cross_line).reconcile()
        self.assertEqual(invoice_1.payment_state, "paid")
        self.assertEqual(invoice_2.payment_state, "paid")
        partial = cross_line.matched_debit_ids | cross_line.matched_credit_ids
        partial_1 = partial.filtered(lambda p: invoice_1.line_ids & (p.debit_move_id | p.credit_move_id))

        invoice_1.js_remove_outstanding_partial(partial_1.id)

        self.assertEqual(cross.state, "cancel")
        self.assertEqual(invoice_1.payment_state, "not_paid")
        self.assertEqual(invoice_2.payment_state, "not_paid")
        self.assertFalse(cross_line.matched_debit_ids | cross_line.matched_credit_ids)


@tagged("l10n_ve_igtf", "-at_install", "post_install")
class TestBreakAdvanceCrossReconciliation(CurrencyFixtureCommon):
    """Cruces de anticipo reales (los crea `js_assign_outstanding_line`): dos líneas, la de la cuenta de anticipo
    (se concilia contra el pago) y la de CxC (se concilia contra la factura). Romper CUALQUIERA de las dos
    conciliaciones con la acción nativa "Romper conciliación" debe cancelar el cruce completo; si no, el
    parcial del otro lado queda, la factura sigue pagada y el anticipo reaparece disponible (doble gasto).
    Las tasas VEF/VEF no intervienen: todo se opera en bolívares en una fecha con tasas sembradas."""

    DATE = "2026-08-01"

    def setUp(self):
        super().setUp()
        self.adv_account = self.env["account.account"].create({
            "name": "Anticipo clientes (prueba cruce real)", "code": "2303ADV",
            "account_type": "liability_current", "reconcile": True, "is_advance_account": True,
            "company_ids": [Command.set([self.company.id])],
        })
        self.partner.default_advance_customer_account_id = self.adv_account
        self.company.advance_payment_igtf_journal_id = self.env["account.journal"].search(
            [("code", "=", "EXCHW"), ("company_id", "=", self.company.id)], limit=1,
        )

    def _new_invoice(self, amount):
        """La factura que devuelve `_invoice` arrastra `default_move_type` en su contexto (viene del Form), y
        eso contamina el asiento de cruce que se crea desde ella: se reabre con un entorno limpio, como llega
        desde el widget."""
        return self.env["account.move"].browse(self._invoice(self.DATE, amount).id)

    def _advance_payment(self, amount):
        """Anticipo en VEF posteado; devuelve (pago, línea de la cuenta de anticipo)."""
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer", "partner_id": self.partner.id,
            "amount": amount, "currency_id": self.vef.id, "journal_id": self.bank["VEF"].id,
            "date": self.DATE, "is_advance_payment": True, "destination_account_id": self.adv_account.id,
        })
        payment.action_post()
        line = payment.move_id.line_ids.filtered(lambda l: l.account_id == self.adv_account)
        self.assertEqual(len(line), 1)
        return payment, line

    def _apply(self, invoice, payment, adv_line):
        """Aplica el anticipo a la factura por el camino real y devuelve el cruce nuevo."""
        before = payment.advanced_move_ids
        self.env.invalidate_all()
        invoice.js_assign_outstanding_line(adv_line.id)
        payment.invalidate_recordset()
        cross = payment.advanced_move_ids - before
        self.assertEqual(len(cross), 1, "Debía crearse exactamente un cruce")
        self.assertEqual(cross.state, "posted")
        return cross

    def _unreconcile(self, lines):
        self.env["account.move.line"].with_context(active_ids=lines.ids).action_unreconcile_match_entries()
        self.env.invalidate_all()

    def _receivable_line(self, invoice):
        return invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

    def _scenario(self, payment_amount=1000.0, invoice_amount=1000.0):
        invoice = self._new_invoice(invoice_amount)
        payment, adv_line = self._advance_payment(payment_amount)
        cross = self._apply(invoice, payment, adv_line)
        return invoice, payment, adv_line, cross

    def _assert_cross_undone(self, cross, invoice, payment, adv_line, available):
        self.assertEqual(cross.state, "cancel", "El cruce debía cancelarse")
        self.assertFalse(cross.origin_payment_advanced_payment_id)
        self.assertNotIn(cross, payment.advanced_move_ids)
        self.assertEqual(invoice.payment_state, "not_paid", "La factura debía quedar pendiente")
        self.assertAlmostEqual(abs(adv_line.amount_residual), available, places=2)
        self.assertEqual(payment.move_id.state, "posted", "El pago origen no debe cancelarse")
        self.assertFalse(cross.line_ids.matched_debit_ids | cross.line_ids.matched_credit_ids)

    def _posted_crosses(self, payment):
        return self.env["account.move"].search([
            ("origin_payment_advanced_payment_id", "=", payment.id), ("state", "=", "posted"),
        ])

    def test_break_from_the_payment_advance_line(self):
        invoice, payment, adv_line, cross = self._scenario()
        self.assertEqual(invoice.payment_state, "paid")
        self.assertFalse(adv_line.amount_residual)

        self._unreconcile(adv_line)

        self._assert_cross_undone(cross, invoice, payment, adv_line, 1000.0)

    def test_break_from_the_cross_advance_line(self):
        invoice, payment, adv_line, cross = self._scenario()
        cross_adv_line = cross.line_ids.filtered(lambda l: l.account_id == self.adv_account)

        self._unreconcile(cross_adv_line)

        self._assert_cross_undone(cross, invoice, payment, adv_line, 1000.0)

    def test_break_from_the_invoice_line(self):
        invoice, payment, adv_line, cross = self._scenario()

        self._unreconcile(self._receivable_line(invoice))

        self._assert_cross_undone(cross, invoice, payment, adv_line, 1000.0)

    def test_partial_application_break_from_the_payment(self):
        """500 de 1000: al romper desde el pago el anticipo vuelve a tener los 1000 completos."""
        invoice, payment, adv_line, cross = self._scenario(payment_amount=1000.0, invoice_amount=500.0)
        self.assertAlmostEqual(abs(adv_line.amount_residual), 500.0, places=2)

        self._unreconcile(adv_line)

        self._assert_cross_undone(cross, invoice, payment, adv_line, 1000.0)

    def test_three_applications_cannot_spend_the_advance_twice(self):
        """Caso real: pago de 1000 con cruces 500 + 500 + 400. Tras romper desde el pago, ningún cruce
        publicado debe sobrevivir y reaplicar no puede gastar más de 1000 en total."""
        payment, adv_line = self._advance_payment(1000.0)
        invoices = [self._new_invoice(amount) for amount in (500.0, 500.0, 400.0)]
        crosses = self.env["account.move"]
        crosses |= self._apply(invoices[0], payment, adv_line)
        crosses |= self._apply(invoices[1], payment, adv_line)
        self.assertFalse(adv_line.amount_residual)

        self._unreconcile(adv_line)

        self.assertEqual(set(crosses.mapped("state")), {"cancel"})
        self.assertFalse(self._posted_crosses(payment))
        self.assertAlmostEqual(abs(adv_line.amount_residual), 1000.0, places=2)
        for invoice in invoices[:2]:
            self.assertEqual(invoice.payment_state, "not_paid")

        self._apply(invoices[2], payment, adv_line)
        self._apply(invoices[0], payment, adv_line)
        self._apply(invoices[1], payment, adv_line)
        spent = sum(
            abs(cross.line_ids.filtered(lambda l: l.account_type == "asset_receivable").balance)
            for cross in self._posted_crosses(payment)
        )
        self.assertAlmostEqual(spent, 1000.0, places=2, msg="El anticipo no puede gastarse dos veces")
        self.assertFalse(adv_line.amount_residual)
        self.assertEqual(invoices[2].payment_state, "paid")
        self.assertEqual(invoices[1].payment_state, "partial")

    def test_invoice_back_to_draft_cancels_its_cross(self):
        invoice, payment, adv_line, cross = self._scenario()

        invoice.button_draft()

        self.assertEqual(cross.state, "cancel")
        self.assertAlmostEqual(abs(adv_line.amount_residual), 1000.0, places=2)
        self.assertFalse(self._posted_crosses(payment))

    def test_invoice_reversal_with_cancel_leaves_no_half_reconciled_cross(self):
        invoice, payment, adv_line, cross = self._scenario()

        self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({"journal_id": invoice.journal_id.id, "reason": "prueba"}).refund_moves()
        self.env.invalidate_all()

        for posted in self._posted_crosses(payment):
            for line in posted.line_ids:
                self.assertTrue(
                    line.matched_debit_ids | line.matched_credit_ids,
                    "Un cruce publicado no puede tener una línea sin conciliar",
                )

    def test_cancel_wizard_cancels_the_cross_only_once(self):
        invoice, payment, adv_line, cross = self._scenario()
        cancelled = []
        original = type(self.env["account.move"]).button_cancel

        def spy(records):
            cancelled.extend(records.ids)
            return original(records)

        wizard = self.env["move.action.cancel.advance.payment.wizard"].create({
            "move_id": invoice.id, "cross_move_ids": [Command.set(cross.ids)], "payment_id": payment.id,
        })
        with patch.object(type(self.env["account.move"]), "button_cancel", spy):
            wizard.action_confirm()
        self.env.invalidate_all()

        self.assertEqual(cancelled.count(cross.id), 1)
        self._assert_cross_undone(cross, invoice, payment, adv_line, 1000.0)

    def test_widget_remove_partial_still_works(self):
        invoice, payment, adv_line, cross = self._scenario()
        cross_receivable = cross.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        partial = cross_receivable.matched_debit_ids | cross_receivable.matched_credit_ids
        self.assertEqual(len(partial), 1)

        invoice.js_remove_outstanding_partial(partial.id)
        self.env.invalidate_all()

        self._assert_cross_undone(cross, invoice, payment, adv_line, 1000.0)

    def test_batch_of_two_payments_and_repeated_call(self):
        invoice_1, payment_1, adv_line_1, cross_1 = self._scenario()
        invoice_2, payment_2, adv_line_2, cross_2 = self._scenario(payment_amount=800.0, invoice_amount=300.0)

        self._unreconcile(adv_line_1 | adv_line_2)

        self._assert_cross_undone(cross_1, invoice_1, payment_1, adv_line_1, 1000.0)
        self._assert_cross_undone(cross_2, invoice_2, payment_2, adv_line_2, 800.0)

        self._unreconcile(adv_line_1 | adv_line_2)
        self.assertEqual(cross_1.state, "cancel")
        self.assertEqual(cross_2.state, "cancel")
