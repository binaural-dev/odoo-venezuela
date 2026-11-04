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
