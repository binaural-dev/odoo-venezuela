from odoo import Command
from odoo.tests import Form, tagged

from .common import ExchangeNoteCommon


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteForeignResidual(ExchangeNoteCommon):
    """La nota de diferencial solo ajusta el balance en VEF, como el asiento nativo: no descuenta divisa
    del residual de la factura ni del pago y cierra siempre por su monto exacto.
    Tasas (VEF por unidad; 2026-01-01 / 03-01 / 05-01 / 08-01): USD 40 / 30 / 50 / 36, EUR 50 / - / - / 45.
    Error original: factura 450, pagado 100, nota de 8.079,42 Bs (~9,19) dejaba 340,81 por pagar y no 350."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd.write({"rate_ids": [
            Command.create({"name": "2026-03-01", "company_rate": 1 / 30.0}),
            Command.create({"name": "2026-05-01", "company_rate": 1 / 50.0}),
        ]})
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.write({
            "active": True,
            "rate_ids": [
                Command.create({"name": "2026-01-01", "company_rate": 1 / 50.0}),
                Command.create({"name": "2026-08-01", "company_rate": 1 / 45.0}),
            ],
        })
        eur_account = cls.env["account.account"].create({
            "name": "Banco EUR Prueba Nota", "code": "BEURN01",
            "account_type": "asset_cash", "currency_id": cls.eur.id,
        })
        cls.eur_bank_journal = cls.env["account.journal"].create({
            "name": "Banco EUR Prueba Nota", "type": "bank", "code": "BEURN",
            "currency_id": cls.eur.id, "company_id": cls.company.id,
            "default_account_id": eur_account.id,
            "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual",
                "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                "payment_account_id": eur_account.id,
            })],
            "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual",
                "payment_method_id": cls.env.ref("account.account_payment_method_manual_out").id,
                "payment_account_id": eur_account.id,
            })],
        })

    def _pay(self, invoice, amount, date):
        """'Registrar pago' de la factura (como en el navegador), en USD."""
        with Form.from_action(self.env, invoice.action_register_payment()) as form:
            form.journal_id = self.usd_bank_journal
            form.payment_date = date
            form.amount = amount
        action = form.record.action_create_payments()
        return self.env["account.payment"].browse(action.get("res_id"))

    def _pay_by_widget(self, invoice, amount, date):
        """Pago en USD creado aparte y cruzado desde el widget: se concilia contra TODAS las cuotas en un mismo
        cruce. El asistente con fecha anterior a los vencimientos solo paga la próxima cuota."""
        payment = self._unreconciled_payment(amount, date)
        invoice.js_assign_outstanding_line(self._receivable(payment.move_id).id)
        return payment

    def _notes(self, invoice):
        return self.env["account.move"].search([("l10n_ve_exchange_invoice_id", "=", invoice.id)])

    def _receivable(self, move):
        return move.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

    def test_note_does_not_reduce_invoice_foreign_residual(self):
        """Pago parcial en USD con tasa distinta (la nota cae del lado de la
        factura): el residual en USD de la factura es exactamente lo no pagado."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        self._pay(invoice, 50.0, "2026-08-01")
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1, "Debía generarse la nota de diferencial cambiario")
        self.assertAlmostEqual(invoice.amount_residual, 50.0, places=2)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(self._receivable(invoice).amount_residual_currency, 50.0, places=2)
        self.assertTrue(self.company.currency_id.is_zero(self._receivable(notes).amount_residual))

    def test_note_does_not_reduce_payment_foreign_residual(self):
        """Pago MAYOR que la factura, con tasa distinta (la nota cae del lado
        del PAGO): a la línea del pago le sobran exactamente los USD no
        aplicados a la factura, no se le descuentan los de la nota."""
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._pay(invoice, 150.0, "2026-01-01")
        self.assertTrue(self.usd.is_zero(invoice.amount_residual))
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1, "Debía generarse la nota de diferencial cambiario")
        payment_line = self._receivable(payment.move_id)
        self.assertAlmostEqual(payment_line.amount_residual_currency, -50.0, places=2)
        self.assertTrue(self.company.currency_id.is_zero(self._receivable(notes).amount_residual))

    def test_note_always_closes_for_exact_amount(self):
        """Matriz fechas de factura x fechas de pago x monto pagado (ganancia y
        pérdida, pagos parciales y totales, y pagos antes o después de la
        factura): en TODOS los casos la nota cierra por completo, el residual
        en USD de la factura es lo no pagado y el pago no queda con USD pegados
        (el pago nunca excede la factura en esta matriz)."""
        dates = ("2026-01-01", "2026-03-01", "2026-05-01", "2026-08-01")
        for invoice_date in dates:
            for payment_date in dates:
                if payment_date == invoice_date:
                    continue
                for amount in (40.0, 100.0):
                    with self.subTest(invoice=invoice_date, payment=payment_date, amount=amount):
                        invoice = self._create_invoice(invoice_date)
                        invoice.with_context(move_action_post_alert=True).action_post()
                        payment = self._pay(invoice, amount, payment_date)
                        self.assertAlmostEqual(invoice.amount_residual, 100.0 - amount, places=2)
                        self.assertTrue(self.usd.is_zero(
                            self._receivable(payment.move_id).amount_residual_currency
                        ))
                        for note in self._notes(invoice):
                            self.assertTrue(
                                self.company.currency_id.is_zero(self._receivable(note).amount_residual),
                                f"La nota {note.name} debía cerrar completa",
                            )

    def _partials_count(self, note):
        line = self._receivable(note)
        return len(line.matched_debit_ids | line.matched_credit_ids)

    def _unreconciled_payment(self, amount, date, currency=None, journal=None):
        """Pago de cliente posteado SIN conciliar (USD por defecto)."""
        currency = currency or self.usd
        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": (journal or self.usd_bank_journal).id,
            "date": date,
        })
        payment.action_post()
        return payment

    def _unreconciled_usd_payment(self, amount, date):
        return self._unreconciled_payment(amount, date)

    def _cross_from_widget(self, invoice, payment):
        """Cruza `payment` desde el widget de créditos pendientes: devuelve
        (monto mostrado, monto aplicado), ambos en la moneda de la factura."""
        line = self._receivable(payment.move_id)
        invoice.invalidate_recordset(["invoice_outstanding_credits_debits_widget"])
        entry = next(
            c for c in invoice.invoice_outstanding_credits_debits_widget["content"] if c["id"] == line.id
        )
        residual_before = invoice.amount_residual
        invoice.js_assign_outstanding_line(line.id)
        return entry["amount"], residual_before - invoice.amount_residual

    def _assert_notes_closed(self, invoice):
        company_currency = self.company.currency_id
        for note in self._notes(invoice):
            self.assertTrue(
                company_currency.is_zero(self._receivable(note).amount_residual),
                f"La nota {note.name} debía cerrar completa",
            )
            self.assertEqual(self._partials_count(note), 1, f"La nota {note.name} debía cerrar con un parcial")

    def test_closing_note_closes_exact_amount_when_line_rate_is_more_favorable(self):
        """Nota de 200 Bs contra una línea con tasa contable más favorable que la de la nota (30 y 36).
        Debe cerrar con un único parcial exacto; sin el tratamiento el motor la cierra con 4 parciales sucesivos.
        Lado factura: NC contra la cuota; lado pago: ND contra el pago. Escenario sintético."""
        company_currency = self.company.currency_id

        invoice = self._create_invoice("2026-03-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        invoice_line = self._receivable(invoice)
        other_payment = self._unreconciled_usd_payment(10.0, "2026-08-01")
        note = invoice_line._create_exchange_difference_note(invoice, other_payment.move_id, 200.0)
        self.assertEqual(note.move_type, "out_refund")
        self.assertTrue(company_currency.is_zero(self._receivable(note).amount_residual),
                        "La NC debía cerrar completa por sus 200 Bs")
        self.assertEqual(self._partials_count(note), 1, "La NC debía cerrar con un solo parcial exacto")
        self.assertAlmostEqual(invoice_line.amount_residual, 3000.0 - 200.0, places=2)
        self.assertAlmostEqual(invoice_line.amount_residual_currency, 100.0, places=2)

        invoice2 = self._create_invoice("2026-08-01")
        invoice2.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_usd_payment(100.0, "2026-03-01")
        payment_line = self._receivable(payment.move_id)
        note = payment_line._create_exchange_difference_note(invoice2, other_payment.move_id, -200.0)
        self.assertEqual(note.move_type, "out_invoice")
        self.assertTrue(company_currency.is_zero(self._receivable(note).amount_residual),
                        "La ND debía cerrar completa por sus 200 Bs")
        self.assertEqual(self._partials_count(note), 1, "La ND debía cerrar con un solo parcial exacto")
        self.assertAlmostEqual(payment_line.amount_residual, -(3000.0 - 200.0), places=2)
        self.assertAlmostEqual(payment_line.amount_residual_currency, -100.0, places=2)

    def test_widget_shows_the_note_as_an_exchange_row(self):
        """En el widget de pagos de la factura la nota de diferencial se
        muestra como una fila de diferencial (como el asiento nativo): marcada
        `is_exchange` (sin botón de desconciliar), con su número, en moneda de la
        compañía y por su monto en Bs -- no como un "pago/reverso" de $9,19 que
        parecería descontar divisa de la factura."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        self._pay(invoice, 50.0, "2026-08-01")
        note = self._notes(invoice)
        self.assertEqual(len(note), 1)

        invoice.invalidate_recordset(["invoice_payments_widget"])
        rows = invoice.invoice_payments_widget["content"]
        note_rows = [row for row in rows if row["move_id"] == note.id]
        self.assertEqual(len(note_rows), 1)
        row = note_rows[0]
        self.assertTrue(row["is_exchange"])
        self.assertEqual(row["currency_id"], self.company.currency_id.id)
        self.assertAlmostEqual(row["amount"], note.amount_total, places=2)

        payment_rows = [row for row in rows if row["move_id"] != note.id]
        self.assertEqual(len(payment_rows), 1)
        self.assertFalse(payment_rows[0]["is_exchange"])
        self.assertEqual(payment_rows[0]["currency_id"], self.usd.id)
        self.assertAlmostEqual(payment_rows[0]["amount"], 50.0, places=2)


    def _widget_rows(self, invoice):
        invoice.invalidate_recordset(["invoice_payments_widget"])
        return (invoice.invoice_payments_widget or {}).get("content", [])

    def test_widget_shows_the_note_that_closes_against_the_payment(self):
        """Pago con tasa mayor que la de la factura (pago de más valor en Bs): la ND cierra contra la línea del
        PAGO, no contra la de la factura. Como el diferencial nativo, SHALL verse en el widget de pagos de la
        factura como fila de diferencial (`is_exchange`), en moneda de la compañía y por su monto en Bs."""
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(100.0, "2026-01-01")
        self._cross_from_widget(invoice, payment)
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.move_type, "out_invoice", "Pago de más valor en Bs: ND")
        note_line = self._receivable(notes)
        payment_line = self._receivable(payment.move_id)
        self.assertTrue(
            self._partial_between(note_line, payment_line),
            "Setup: la nota debía cerrar contra la línea del PAGO",
        )
        self.assertFalse(self._partial_between(note_line, self._receivable(invoice)))

        rows = self._widget_rows(invoice)
        note_rows = [row for row in rows if row["move_id"] == notes.id]
        self.assertEqual(len(note_rows), 1, "La nota que cierra contra el pago debía verse en el widget")
        self.assertTrue(note_rows[0]["is_exchange"])
        self.assertEqual(note_rows[0]["currency_id"], self.company.currency_id.id)
        self.assertAlmostEqual(note_rows[0]["amount"], notes.amount_total, places=2)
        payment_rows = [row for row in rows if row["move_id"] != notes.id]
        self.assertEqual(len(payment_rows), 1)
        self.assertFalse(payment_rows[0]["is_exchange"])
        self.assertAlmostEqual(payment_rows[0]["amount"], 100.0, places=2)

    def test_widget_note_row_disappears_when_the_partial_is_broken(self):
        """Al desconciliar el pago la nota se revierte y su fila deja de verse."""
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(100.0, "2026-01-01")
        self._cross_from_widget(invoice, payment)
        note = self._notes(invoice)
        self.assertTrue([row for row in self._widget_rows(invoice) if row["move_id"] == note.id])

        partial = self._partial_between(self._receivable(invoice), self._receivable(payment.move_id))
        invoice.js_remove_outstanding_partial(partial.id)

        self.assertTrue(note.reversal_move_ids, "La nota debía revertirse")
        self.assertFalse([row for row in self._widget_rows(invoice) if row["move_id"] == note.id])

    def test_widget_shows_one_row_per_installment_note_that_closes_against_the_payment(self):
        """Dos cuotas, notas contra la MISMA línea del pago: una fila por nota, sin duplicados."""
        invoice, _installments = self._two_installment_invoice("2026-08-01")
        self._pay_by_widget(invoice, 100.0, "2026-01-01")
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 2)
        rows = self._widget_rows(invoice)
        for note in notes:
            self.assertEqual(len([row for row in rows if row["move_id"] == note.id]), 1)

    def _two_installments_term(self):
        return self.env["account.payment.term"].create({
            "name": "50/50 Prueba Nota",
            "line_ids": [
                Command.create({"value": "percent", "value_amount": 50.0, "delay_type": "days_after", "nb_days": 0}),
                Command.create({"value": "percent", "value_amount": 50.0, "delay_type": "days_after", "nb_days": 30}),
            ],
        })

    def test_installments_get_one_note_per_installment(self):
        """Factura con DOS cuotas: como el asiento de diferencial nativo, cada
        línea con residual recibe su propia nota (antes solo se emitía una por
        par factura/pago y la diferencia de la otra cuota se perdía), y al
        romper la conciliación del pago se revierten todas."""
        invoice = self._create_invoice("2026-01-01")
        with Form(invoice) as form:
            form.invoice_payment_term_id = self._two_installments_term()
        invoice.with_context(move_action_post_alert=True).action_post()
        installments = self._receivable(invoice)
        self.assertEqual(len(installments), 2, "Setup: la factura debía quedar con dos cuotas")

        payment = self._pay(invoice, 100.0, "2026-08-01")

        notes = self._notes(invoice)
        self.assertEqual(len(notes), 2, "Debía emitirse una nota por cuota")
        self.assertEqual(len(notes.mapped("l10n_ve_exchange_line_id")), 2)
        self._assert_notes_closed(invoice)
        for line in installments:
            self.assertTrue(self.company.currency_id.is_zero(line.amount_residual))
            self.assertTrue(self.usd.is_zero(line.amount_residual_currency))
        self.assertTrue(self.usd.is_zero(invoice.amount_residual))
        payment_line = self._receivable(payment.move_id)
        self.assertTrue(self.company.currency_id.is_zero(payment_line.amount_residual))
        self.assertTrue(self.usd.is_zero(payment_line.amount_residual_currency))

        payment_line.remove_move_reconcile()
        self.assertTrue(all(note.reversal_move_ids for note in notes), "Debían revertirse todas las notas")

    def _two_installment_invoice(self, invoice_date):
        invoice = self._create_invoice(invoice_date)
        with Form(invoice) as form:
            form.invoice_payment_term_id = self._two_installments_term()
        invoice.with_context(move_action_post_alert=True).action_post()
        installments = self._receivable(invoice).sorted("id")
        self.assertEqual(len(installments), 2, "Setup: la factura debía quedar con dos cuotas")
        return invoice, installments

    def _partial_between(self, installment, payment_line):
        return self.env["account.partial.reconcile"].search([
            ("debit_move_id", "=", installment.id), ("credit_move_id", "=", payment_line.id),
        ])

    def test_installments_with_residual_on_the_payment_side_get_one_note_each(self):
        """Pago anterior a la factura (residual del lado del PAGO): las dos notas
        cierran contra la MISMA línea del pago y aun así cada cuota recibe la
        suya. Si la llave fuera la línea que cierra, la segunda quedaría
        bloqueada por la guarda de duplicados y su diferencia se perdería."""
        invoice, installments = self._two_installment_invoice("2026-08-01")
        payment = self._pay_by_widget(invoice, 100.0, "2026-01-01")

        notes = self._notes(invoice)
        self.assertEqual(len(notes), 2, "Debía emitirse una nota por cuota")
        self.assertEqual(set(notes.mapped("l10n_ve_exchange_line_id").ids), set(installments.ids))
        self.assertTrue(all(note.move_type == "out_invoice" for note in notes), "Ganancia: ND")
        self._assert_notes_closed(invoice)
        payment_line = self._receivable(payment.move_id)
        self.assertTrue(self.company.currency_id.is_zero(payment_line.amount_residual))
        self.assertTrue(self.usd.is_zero(payment_line.amount_residual_currency))
        self.assertTrue(self.usd.is_zero(invoice.amount_residual))

    def _assert_breaking_one_installment_reverses_only_its_note(self, invoice_date, payment_date):
        invoice, installments = self._two_installment_invoice(invoice_date)
        payment = self._pay_by_widget(invoice, 100.0, payment_date)
        payment_line = self._receivable(payment.move_id)
        notes = self._notes(invoice)
        note_of = {note.l10n_ve_exchange_line_id: note for note in notes}
        self.assertEqual(len(note_of), 2, "Setup: una nota por cuota")
        first, second = installments

        invoice.js_remove_outstanding_partial(self._partial_between(first, payment_line).id)

        self.assertTrue(note_of[first].reversal_move_ids, "La nota de la cuota rota debía revertirse")
        self.assertFalse(note_of[second].reversal_move_ids, "La nota de la otra cuota debía seguir vigente")
        self.assertTrue(self._partial_between(second, payment_line), "La otra cuota debía seguir cruzada")
        self.assertFalse(self._partial_between(first, payment_line))

    def test_breaking_one_installment_partial_reverses_only_its_note(self):
        """Residual del lado de la factura: una nota por cuota, cada una ligada a
        su cuota."""
        self._assert_breaking_one_installment_reverses_only_its_note("2026-01-01", "2026-08-01")

    def test_breaking_one_installment_partial_with_residual_on_payment_side(self):
        """Residual del lado del pago: las dos notas cierran contra la misma línea
        del pago, pero al romper el parcial de una cuota solo se revierte la de
        esa cuota."""
        self._assert_breaking_one_installment_reverses_only_its_note("2026-08-01", "2026-01-01")


    def test_widget_vef_payment_on_usd_invoice_matches_shown_amount(self):
        """Pago en VEF anterior a la factura en USD, cruzado desde el widget:
        se aplica lo mostrado (100 USD) y, como la tasa del widget coincide con
        la contable del pago, no sobra diferencial."""
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(
            3600.0, "2026-01-01", currency=self.company.currency_id, journal=self.vef_bank_journal,
        )
        shown, applied = self._cross_from_widget(invoice, payment)
        self.assertAlmostEqual(shown, 100.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self._assert_notes_closed(invoice)
        payment_line = self._receivable(payment.move_id)
        self.assertTrue(self.company.currency_id.is_zero(payment_line.amount_residual))

    def test_widget_usd_payment_on_vef_invoice_issues_note_for_the_difference(self):
        """Factura en VEF pagada con USD anteriores, desde el widget: se aplica
        lo mostrado (80 USD x 36 = 2.880 Bs) y la diferencia con el balance del
        pago (80 x 40 = 3.200 Bs) sale como diferencial cambiario, o sea una
        nota -- igual que cualquier diferencial nativo de Odoo."""
        invoice = self._create_invoice_company_currency("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(80.0, "2026-01-01")
        shown, applied = self._cross_from_widget(invoice, payment)
        self.assertAlmostEqual(shown, 80.0 * 36.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1, "La diferencia debía emitirse como nota")
        self.assertEqual(notes.move_type, "out_invoice", "Pago de más valor en Bs: ND (ganancia)")
        self.assertAlmostEqual(notes.amount_total, 320.0, places=2)
        self.assertEqual(notes.l10n_ve_exchange_line_id, self._receivable(invoice))
        self._assert_notes_closed(invoice)
        payment_line = self._receivable(payment.move_id)
        self.assertTrue(self.company.currency_id.is_zero(payment_line.amount_residual))
        self.assertTrue(self.usd.is_zero(payment_line.amount_residual_currency))

    def test_widget_eur_payment_on_usd_invoice_closes_everything(self):
        """Pago en una tercera moneda cruzado desde el widget: lo aplicado es lo mostrado
        (72 EUR x 45 / 36 = 90 USD) y el pago y las notas que salgan quedan cerrados."""
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(72.0, "2026-01-01", currency=self.eur, journal=self.eur_bank_journal)
        shown, applied = self._cross_from_widget(invoice, payment)
        self.assertAlmostEqual(shown, 90.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self._assert_notes_closed(invoice)
        payment_line = self._receivable(payment.move_id)
        self.assertTrue(self.company.currency_id.is_zero(payment_line.amount_residual))
        self.assertTrue(self.eur.is_zero(payment_line.amount_residual_currency))


    def test_widget_usd_overpayment_on_vef_invoice_settles_both_sides(self):
        """Pago en USD mayor que la factura en VEF, cruzado desde el widget: un mismo parcial deja diferencial
        en la línea de la factura (NC de redondeo) y en la del pago (ND). Cada uno debe emitir su nota,
        como el asiento nativo, que lo cierra en un solo asiento con las dos líneas."""
        invoice = self._create_invoice_company_currency("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(200.0, "2026-01-01")
        self._cross_from_widget(invoice, payment)
        self.assertTrue(self.company.currency_id.is_zero(invoice.amount_residual))
        payment_line = self._receivable(payment.move_id)
        self.assertAlmostEqual(payment_line.amount_residual_currency, -88.89, places=2)
        self.assertAlmostEqual(payment_line.amount_residual, -88.89 * 40.0, places=2)
        self._assert_notes_closed(invoice)
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 2, "Una nota por cada línea con diferencial (factura y pago)")
        credit_note = notes.filtered(lambda n: n.move_type == "out_refund")
        debit_note = notes.filtered(lambda n: n.move_type == "out_invoice")
        self.assertAlmostEqual(credit_note.amount_total, 0.04, places=2, msg="NC de redondeo del lado de la factura")
        self.assertAlmostEqual(debit_note.amount_total, 444.44, places=2, msg="ND del lado del pago")

    def test_closing_note_context_does_not_touch_partials_without_a_note_line(self):
        """El contexto de cierre de nota sigue vivo en conciliaciones anidadas (p. ej. asientos de caja de
        impuestos). Si ninguna línea del parcial es de una nota, no se pone en 0 el monto en divisa."""
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(100.0, "2026-08-01")
        invoice_line = self._receivable(invoice)
        (invoice_line + self._receivable(payment.move_id)).with_context(
            l10n_ve_exchange_closing_note=True,
        ).reconcile()
        partial = invoice_line.matched_debit_ids | invoice_line.matched_credit_ids
        self.assertAlmostEqual(partial.debit_amount_currency or partial.credit_amount_currency, 100.0, places=2)
        self.assertTrue(self.usd.is_zero(invoice_line.amount_residual_currency))
        self.assertEqual(invoice.payment_state, "paid")

    def test_is_exchange_note_line_without_move_is_false(self):
        """Una línea sin asiento no es de nota (antes devolvía False; el `ensure_one()` la hacía reventar)."""
        self.assertFalse(self.env["account.move.line"].new()._is_exchange_note_line())

    def _use_rising_rates(self):
        """Tasas crecientes, como en la economía venezolana: enero 36, agosto 40 Bs/$."""
        for rate in self.usd.rate_ids:
            if str(rate.name) == "2026-01-01":
                rate.company_rate = 1 / 36.0
            elif str(rate.name) == "2026-08-01":
                rate.company_rate = 1 / 40.0
        self.env.invalidate_all()

    def _rising_rates_invoice_and_payment(self, amount):
        """Factura de $100 del 01-08 (4.000 Bs a 40) y pago en Bs anterior, del 01-01 (a 36 vale $amount/36)."""
        self._use_rising_rates()
        invoice = self._create_invoice("2026-08-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(
            amount, "2026-01-01", currency=self.company.currency_id, journal=self.vef_bank_journal,
        )
        return invoice, payment

    def test_rising_rates_widget_values_a_bs_payment_at_the_invoice_date(self):
        """Pago de 3.600 Bs del 01-01 (36) sobre una factura de $100 del 01-08 (40): el widget lo valora a la tasa
        de la factura (3.600/40 = $90), aplica lo mostrado y la factura queda parcial con $10 (400 Bs), sin notas.
        Es la decisión funcional documentada en la openspec de `l10n_ve_igtf`."""
        invoice, payment = self._rising_rates_invoice_and_payment(3600.0)
        shown, applied = self._cross_from_widget(invoice, payment)
        self.assertAlmostEqual(shown, 90.0, places=2)
        self.assertAlmostEqual(applied, 90.0, places=2)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(self._receivable(invoice).amount_residual_currency, 10.0, places=2)
        self.assertAlmostEqual(self._receivable(invoice).amount_residual, 400.0, places=2)
        self.assertTrue(self.company.currency_id.is_zero(self._receivable(payment.move_id).amount_residual))
        self.assertFalse(self._notes(invoice), "El widget no genera diferencial en este caso")

    def test_rising_rates_manual_reconcile_keeps_the_native_valuation(self):
        """Mismas líneas conciliadas a mano desde apuntes: valoración nativa (fecha del pago, 3.600/36 = $100); la
        factura queda pagada y la diferencia de 400 Bs sale como una NC. Lo que no cambia este PR."""
        invoice, payment = self._rising_rates_invoice_and_payment(3600.0)
        (self._receivable(invoice) + self._receivable(payment.move_id)).reconcile()
        self.assertEqual(invoice.payment_state, "paid")
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.move_type, "out_refund")
        self.assertAlmostEqual(notes.amount_total, 400.0, places=2)
        self.assertTrue(self.company.currency_id.is_zero(self._receivable(payment.move_id).amount_residual))

    def test_rising_rates_widget_with_a_payment_worth_exactly_the_invoice(self):
        """Pago de 4.000 Bs del 01-01: a la tasa de la factura (40) vale justo $100; el widget lo consume
        completo, sin notas."""
        invoice, payment = self._rising_rates_invoice_and_payment(4000.0)
        shown, applied = self._cross_from_widget(invoice, payment)
        self.assertAlmostEqual(shown, 100.0, places=2)
        self.assertAlmostEqual(applied, 100.0, places=2)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(self.company.currency_id.is_zero(self._receivable(payment.move_id).amount_residual))
        self.assertFalse(self._notes(invoice))

    def test_rising_rates_manual_reconcile_of_a_bigger_payment_leaves_credit_and_a_note(self):
        """Pago de 4.000 Bs conciliado a mano: nativo valora a la tasa del pago ($111,11), la factura queda
        pagada, al pago le sobran 400 Bs y se emite una NC de 400 Bs."""
        invoice, payment = self._rising_rates_invoice_and_payment(4000.0)
        (self._receivable(invoice) + self._receivable(payment.move_id)).reconcile()
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(self._receivable(payment.move_id).amount_residual, -400.0, places=2)
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.move_type, "out_refund")
        self.assertAlmostEqual(notes.amount_total, 400.0, places=2)

    def test_rate_rise_at_collection_emits_a_debit_note_that_the_payment_settles_with_the_invoice(self):
        """Razón fiscal de la ND: si la tasa SUBE al cobrar, el cliente entrega más Bs que los de la factura
        (3.600 Bs a 36; cobro de $100 a 40 = 4.000 Bs) y esa diferencia (400 Bs) se documenta con una ND ligada a
        la factura. El pago extingue AMBAS cuentas por cobrar (factura 3.600 + ND 400, saldo 0) y, al
        desconciliar el pago, se deshace todo y la ND se revierte."""
        self._use_rising_rates()
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._unreconciled_payment(100.0, "2026-08-01")
        invoice_line = self._receivable(invoice)
        payment_line = self._receivable(payment.move_id)
        self._cross_from_widget(invoice, payment)

        note = self._notes(invoice)
        self.assertEqual(len(note), 1)
        self.assertEqual(note.move_type, "out_invoice", "Sube la tasa: Nota de Débito")
        self.assertEqual(note.debit_origin_id, invoice, "La ND queda ligada a la factura de origen")
        self.assertAlmostEqual(note.amount_total, 400.0, places=2)
        self.assertEqual(note.state, "posted")

        note_line = self._receivable(note)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))
        self.assertTrue(self.company.currency_id.is_zero(payment_line.amount_residual), "El pago queda aplicado")
        self.assertTrue(self.usd.is_zero(payment_line.amount_residual_currency))
        invoice_partial = self._partial_between(invoice_line, payment_line)
        note_partial = self._partial_between(note_line, payment_line)
        self.assertAlmostEqual(invoice_partial.amount, 3600.0, places=2, msg="El pago liquida la factura")
        self.assertAlmostEqual(note_partial.amount, 400.0, places=2, msg="y la ND con el excedente")

        invoice.js_remove_outstanding_partial(invoice_partial.id)

        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertTrue(note.reversal_move_ids, "Al desconciliar el pago la ND se revierte")
        self.assertFalse(self._partial_between(note_line, payment_line))
        self.assertAlmostEqual(payment_line.amount_residual, -4000.0, places=2, msg="El pago queda disponible completo")
