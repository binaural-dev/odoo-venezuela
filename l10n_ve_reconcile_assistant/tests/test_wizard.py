from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged

from .common import ReconcileAssistantCommon


@tagged("l10n_ve_reconcile_assistant", "-at_install", "post_install")
class TestAssistantWizard(ReconcileAssistantCommon):
    """El asistente abierto con el formulario: su vista previa debe ser lo que de verdad se aplica al
    confirmar, factura por factura, en el orden elegido y recalculando lo que queda del origen."""

    def _lines(self, invoices, origin):
        return sum((self._receivable_line(invoice) for invoice in invoices), origin)

    def _confirm(self, wizard):
        """Confirma y devuelve lo aplicado a cada factura (baja de su residual, en su moneda)."""
        invoices = wizard.item_ids.sorted("sequence").invoice_id
        before = {invoice.id: invoice.amount_residual for invoice in invoices}
        action = wizard.action_confirm()
        self.assertEqual(action, {"type": "ir.actions.act_window_close"})
        invoices.invalidate_recordset()
        return {invoice.id: before[invoice.id] - invoice.amount_residual for invoice in invoices}

    def _assert_preview_matches(self, wizard, applied):
        """Lo previsto para cada factura (suma de sus filas, si varios orígenes la pagan) es lo aplicado."""
        previewed = {}
        for item in wizard.item_ids:
            previewed[item.invoice_id.id] = previewed.get(item.invoice_id.id, 0.0) + item.apply_amount
        for invoice_id, total in previewed.items():
            self.assertAlmostEqual(
                total, applied[invoice_id], places=2,
                msg=f"La vista previa de la factura {invoice_id} no coincide con lo aplicado",
            )

    def test_payment_vef_two_usd_invoices_preview_equals_result(self):
        """Pago de 6.000 Bs a la tasa 36 = 166,67 USD contra facturas de 100 y 80 USD: la primera se paga
        completa y la segunda queda con 13,33 pendientes."""
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 6000.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(self._lines(first + second, payment))
        self.assertEqual(wizard.case, "payment")
        self.assertEqual(wizard.origin_line_ids, payment)
        self.assertEqual(wizard.invoice_line_ids, self._receivable_line(first) + self._receivable_line(second))
        self.assertEqual(wizard.scenario_label, "1 payment against 2 invoices")
        self.assertEqual(wizard.item_ids.invoice_id, first + second)
        rows = wizard.item_ids.sorted("sequence")
        self.assertAlmostEqual(rows[0].apply_amount, 100.0, places=2)
        self.assertAlmostEqual(rows[1].widget_amount, 66.67, places=2)
        self.assertAlmostEqual(rows[1].pending_after, 13.33, places=2)
        self.assertTrue(wizard.pending_warning)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(first.payment_state, "paid")
        self.assertEqual(second.payment_state, "partial")

    def test_dragging_an_invoice_recalculates_and_the_new_order_is_applied(self):
        """El usuario arrastra la segunda factura a la primera posición (el widget handle reasigna la
        secuencia de las filas): la vista previa se recalcula y al confirmar se respeta el nuevo orden."""
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 6000.0, self.vef, "2026-08-01")
        action = self._lines(first + second, payment).action_l10n_ve_reconcile_assistant()
        with Form.from_action(self.env, action) as form:
            self.assertEqual(len(form.item_ids), 2)
            with form.item_ids.edit(0) as row:
                self.assertEqual(row.invoice_id, first)
                row.sequence = 40
            with form.item_ids.edit(1) as row:
                self.assertEqual(row.invoice_id, second)
                row.sequence = 20
            with form.item_ids.edit(0) as row:
                self.assertAlmostEqual(row.apply_amount, 86.67, places=2)
                self.assertAlmostEqual(row.pending_after, 13.33, places=2)
            with form.item_ids.edit(1) as row:
                self.assertAlmostEqual(row.apply_amount, 80.0, places=2)
                self.assertAlmostEqual(row.pending_after, 0.0, places=2)
            self.assertTrue(form.pending_warning)
        wizard = form.save()
        items = wizard.item_ids.sorted("sequence")
        self.assertEqual(items.invoice_id, second + first)
        self.assertAlmostEqual(items[0].apply_amount, 80.0, places=2)
        self.assertAlmostEqual(items[1].apply_amount, 86.67, places=2)
        applied = self._confirm(wizard)
        self.assertEqual(second.payment_state, "paid")
        self.assertEqual(first.payment_state, "partial")
        self._assert_preview_matches(wizard, applied)

    def test_single_invoice_exhausting_the_origin_skips_the_rest(self):
        """Si la primera factura consume todo el origen, la segunda no se toca."""
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(self._lines(first + second, payment))
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(first.payment_state, "paid")
        self.assertEqual(second.payment_state, "not_paid")
        self.assertTrue(payment.reconciled)

    def test_one_invoice_with_usd_payment_on_vef_invoice(self):
        invoice = self._invoice("2026-08-01", 4000.0)
        payment = self._outstanding_line(self.bank["USD"], 80.0, self.usd, "2026-01-01")
        wizard = self._open_assistant(self._lines(invoice, payment))
        item = wizard.item_ids
        self.assertAlmostEqual(item.widget_amount, 80.0 * 36.0, places=2)
        self.assertEqual(str(item.conversion_date), "2026-08-01")
        self.assertAlmostEqual(item.rate, 36.0, places=4)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)

    def test_advance_with_igtf_two_invoices_preview_equals_result(self):
        """Anticipo en USD con diario de IGTF: un cruce por factura; el primero consume monto más IGTF y el
        segundo recibe lo que queda."""
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        advance = self._advance_payment(self.bank["USD"], 170.0)
        wizard = self._open_assistant(self._lines(first + second, advance))
        self.assertEqual(wizard.case, "advance")
        self.assertIn("IGTF journal", wizard.item_ids[0].origin_conditions)
        self.assertEqual(wizard.scenario_label, "1 advance against 2 invoices")
        rows = wizard.item_ids.sorted("sequence")
        self.assertAlmostEqual(rows[0].igtf_amount, 3.0, places=2)
        before = self.env["account.move"].search_count([("is_advance_move", "=", True)])
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(self.env["account.move"].search_count([("is_advance_move", "=", True)]) - before, 2)
        self.assertTrue(advance.reconciled)

    def test_advance_smaller_than_invoice_plus_igtf_carves_igtf_from_it(self):
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        advance = self._advance_payment(self.bank["USD"], 100.0)
        wizard = self._open_assistant(self._lines(invoice, advance))
        item = wizard.item_ids
        self.assertAlmostEqual(item.igtf_amount, 3.0, places=2)
        self.assertAlmostEqual(item.apply_amount, 97.0, places=2)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(invoice.payment_state, "partial")

    def test_advance_without_igtf_journal(self):
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        advance = self._advance_payment(self.bank["VEF"], 3600.0)
        wizard = self._open_assistant(self._lines(invoice, advance))
        self.assertNotIn("IGTF journal", wizard.item_ids.origin_conditions)
        self.assertEqual(wizard.item_ids.igtf_amount, 0.0)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(invoice.payment_state, "paid")

    def test_blocked_selection_shows_reasons_and_cannot_be_confirmed(self):
        advance = self._advance_payment(self.bank["USD"], 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(advance + payment)
        self.assertEqual(wizard.case, "blocked")
        self.assertIn("against an invoice", wizard.blocked_reason)
        self.assertFalse(wizard.item_ids)
        self.assertFalse(wizard.origin_line_ids)
        self.assertFalse(wizard.scenario_label)
        with self.assertRaisesRegex(UserError, "against an invoice"):
            wizard.action_confirm()

    def test_selection_not_handled_is_reported(self):
        first = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        second = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(first + second)
        self.assertEqual(wizard.case, "blocked")
        self.assertIn("not a payment or advance", wizard.blocked_reason)

    def test_missing_widget_amount_blocks_the_assistant(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        with patch.object(self.env.registry["l10n_ve.reconcile.assistant"], "_widget_entry",
                          return_value=None):
            wizard = self._open_assistant(self._lines(invoice, payment))
        self.assertEqual(wizard.case, "blocked")
        self.assertIn(invoice.name, wizard.blocked_reason)

    def test_confirm_rejects_a_selection_that_changed_after_opening(self):
        invoice = self._invoice("2026-08-01", 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(self._lines(invoice, payment))
        invoice.js_assign_outstanding_line(payment.id)
        with self.assertRaisesRegex(UserError, "selection changed"):
            wizard.action_confirm()

    def test_failure_in_second_invoice_rolls_back_the_first(self):
        """Una sola transacción: si la segunda aplicación falla, la primera no queda hecha."""
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 6000.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(self._lines(first + second, payment))
        original = self.env.registry["account.move"].js_assign_outstanding_line

        def failing(move, line_id):
            if move == second:
                raise UserError("falla simulada")
            return original(move, line_id)

        with self.assertRaisesRegex(UserError, "falla simulada"), self.env.cr.savepoint():
            with patch.object(self.env.registry["account.move"], "js_assign_outstanding_line", failing):
                wizard.action_confirm()
        first.invalidate_recordset()
        self.assertEqual(first.payment_state, "not_paid")
        self.assertFalse(payment.reconciled)


    def test_one_payment_against_three_invoices_has_no_limit(self):
        invoices = [self._invoice("2026-08-01", price, self.usd) for price in (50.0, 40.0, 30.0)]
        payment = self._outstanding_line(self.bank["VEF"], 4320.0, self.vef, "2026-08-01")
        lines = payment + self._receivable_line(invoices[0]) + self._receivable_line(invoices[1]) \
            + self._receivable_line(invoices[2])
        wizard = self._open_assistant(lines)
        self.assertEqual(wizard.scenario_label, "1 payment against 3 invoices")
        self.assertEqual(len(wizard.item_ids), 3)
        self.assertFalse(wizard.pending_warning)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertTrue(all(invoice.payment_state == "paid" for invoice in invoices))

    def test_a_payment_bigger_than_the_invoice_keeps_its_balance_like_the_widget(self):
        """Igual que el widget de la factura: el pago de 4.000 Bs (111,11 USD) paga la factura de 100 USD y
        conserva 400 Bs como pago pendiente. El asistente no lo bloquea y lo muestra en "Saldo origen"."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 4000.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(self._receivable_line(invoice) + payment)
        self.assertEqual(wizard.case, "payment")
        self.assertAlmostEqual(wizard.item_ids.origin_remaining, 400.0, places=2)
        self.assertIn("400.00", wizard.origin_summary)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertFalse(payment.reconciled)
        self.assertAlmostEqual(abs(payment.amount_residual_currency), 400.0, places=2)

    def test_part_of_an_advance_against_two_invoices_keeps_the_balance_as_previewed(self):
        """Anticipo de 300 USD con IGTF contra facturas de 100 y 80 USD: cada una genera su propio cruce con
        su IGTF (3,00 y 2,40) y el anticipo queda con 114,60 USD. El saldo previsto en cada fila es el real."""
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        advance = self._advance_payment(self.bank["USD"], 300.0)
        wizard = self._open_assistant(self._lines(first + second, advance))
        rows = wizard.item_ids.sorted("sequence")
        self.assertAlmostEqual(rows[0].igtf_amount, 3.0, places=2)
        self.assertAlmostEqual(rows[1].igtf_amount, 2.4, places=2)
        self.assertAlmostEqual(rows[0].origin_before, 300.0, places=2)
        self.assertAlmostEqual(rows[1].origin_before, 197.0, places=2)
        self.assertAlmostEqual(rows[0].origin_remaining, 197.0, places=2)
        self.assertAlmostEqual(rows[1].origin_remaining, 114.6, places=2)
        # Lo que sale del anticipo es lo de cada factura más su IGTF: 103,00 + 82,40 = 185,40 de 300, no más
        self.assertAlmostEqual(rows[0].origin_applied, 103.0, places=2)
        self.assertAlmostEqual(rows[1].origin_applied, 82.4, places=2)
        self.assertAlmostEqual(sum(rows.mapped("origin_applied")) + rows[1].origin_remaining, 300.0, places=2)
        self.assertIn("185.40", wizard.origin_summary)
        self.assertIn("300.00", wizard.origin_summary)
        self.assertIn("114.60", wizard.origin_summary)
        before = self.env["account.move"].search_count([("is_advance_move", "=", True)])
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(self.env["account.move"].search_count([("is_advance_move", "=", True)]) - before, 2)
        self.assertTrue(first.payment_state == second.payment_state == "paid")
        self.assertFalse(advance.reconciled)
        self.assertAlmostEqual(abs(advance.amount_residual_currency), rows[1].origin_remaining, places=2)

    def test_part_of_a_bolivar_advance_crossed_at_each_invoice_date(self):
        """Anticipo de 8.000 Bs del 01/01 contra facturas de 100 USD (01/01, tasa 40) y 80 USD (01/08, tasa
        36). Cada cruce convierte a la fecha de su factura, pero no con la tasa exacta: consume `saldo x base /
        monto del widget` con el monto del widget ya redondeado (4.000 x 80 / 111,11 = 2.880,03 Bs en vez de
        2.880,00), así que al anticipo le quedan 1.119,97 Bs y no 1.120. La vista previa muestra ese valor real."""
        first = self._invoice("2026-01-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        advance = self._advance_payment(self.bank["VEF"], 8000.0, date="2026-01-01")
        wizard = self._open_assistant(self._lines(first + second, advance))
        rows = wizard.item_ids.sorted("sequence")
        self.assertEqual([str(row.conversion_date) for row in rows], ["2026-01-01", "2026-08-01"])
        self.assertAlmostEqual(rows[0].rate, 40.0, places=4)
        self.assertAlmostEqual(rows[1].rate, 36.0, places=4)
        self.assertAlmostEqual(rows[1].widget_amount, 111.11, places=2)
        self.assertAlmostEqual(rows[0].origin_remaining, 4000.0, places=2)
        self.assertAlmostEqual(rows[1].origin_remaining, 1119.97, places=2)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertTrue(first.payment_state == second.payment_state == "paid")
        self.assertAlmostEqual(abs(advance.amount_residual_currency), rows[1].origin_remaining, places=2)

    def test_the_residual_of_an_overpayment_is_an_advance_that_can_be_crossed(self):
        """Pagar de más desde la factura deja un asiento "RESTANTE DE PAGO EN DIVISA" (`is_advance_move`,
        con el pago en `origin_payment_advanced_payment_id` y sin `origin_payment_id`). Su línea en la
        cuenta de anticipos es un anticipo válido, el widget de otra factura lo ofrece, y el asistente
        debe tomarlo como tal y leer el pago como el motor (diario con IGTF incluido)."""
        today = fields.Date.today()
        first = self._invoice(today, 100.0, self.usd)
        second = self._invoice(today, 40.0, self.usd)
        with Form.from_action(self.env, first.action_register_payment()) as form:
            form.journal_id = self.bank["USD"]
            form.payment_date = today
            form.save()
            form.amount = 150.0
            form.save()
        payment = self.env["account.payment"].browse(form.record.action_create_payments().get("res_id"))
        residual = payment.advanced_move_ids
        self.assertTrue(residual.is_advance_move)
        self.assertFalse(residual.origin_payment_id)
        advance_line = residual.line_ids.filtered(
            lambda line: line.account_id.is_advance_account and line.credit > 0)
        self.assertEqual(advance_line._l10n_ve_reconcile_kind(), "advance")
        self.assertEqual((residual.line_ids - advance_line)._l10n_ve_reconcile_kind(), "cross")
        wizard = self._open_assistant(advance_line + self._receivable_line(second))
        self.assertEqual(wizard.case, "advance")
        row = wizard.item_ids
        self.assertIn("IGTF journal", row.origin_conditions)
        self.assertAlmostEqual(row.igtf_amount, 1.2, places=2)
        offered = wizard._widget_entry(second, advance_line)
        self.assertAlmostEqual(row.widget_amount, offered["amount"], places=2)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertEqual(second.payment_state, "paid")
        self.assertAlmostEqual(abs(advance_line.amount_residual_currency), row.origin_remaining, places=2)

    def test_part_of_a_bolivar_advance_that_keeps_its_value_uses_the_advance_date(self):
        """Con "mantener valor" ambos cruces convierten a la fecha del anticipo (tasa 40): 4.000 y 3.200 Bs,
        quedan 800 Bs."""
        first = self._invoice("2026-01-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        advance = self._advance_payment(self.bank["VEF"], 8000.0, date="2026-01-01", keep=True)
        wizard = self._open_assistant(self._lines(first + second, advance))
        rows = wizard.item_ids.sorted("sequence")
        self.assertIn("Keeps the value", rows[0].origin_conditions)
        self.assertEqual([str(row.conversion_date) for row in rows], ["2026-01-01", "2026-01-01"])
        self.assertAlmostEqual(rows[1].origin_remaining, 800.0, places=2)
        applied = self._confirm(wizard)
        self._assert_preview_matches(wizard, applied)
        self.assertAlmostEqual(abs(advance.amount_residual_currency), 800.0, places=2)

    def test_several_origins_are_blocked_in_the_wizard(self):
        invoice = self._invoice("2026-08-01", 100.0)
        first = self._outstanding_line(self.bank["VEF"], 60.0, self.vef, "2026-08-01")
        second = self._outstanding_line(self.bank["VEF"], 40.0, self.vef, "2026-08-01")
        wizard = self._open_assistant(self._receivable_line(invoice) + first + second)
        self.assertEqual(wizard.case, "blocked")
        self.assertIn("single payment or advance", wizard.blocked_reason)
        self.assertFalse(wizard.item_ids)


    def _apply_checking_the_real_widget(self, wizard):
        """Aplica fila por fila como lo haría el usuario desde cada factura y, justo antes de cada una,
        compara lo que muestra el widget REAL de esa factura (con el residual que el origen tiene en ese
        momento) con la fila de la vista previa: monto ofrecido, fecha de conversión y lo que se aplica."""
        for item in wizard.item_ids.sorted("sequence"):
            invoice, origin = item.invoice_id, item.origin_line_id
            entry = wizard._widget_entry(invoice, origin)
            self.assertIsNotNone(entry, f"El widget de {invoice.name} no ofrece el origen")
            self.assertAlmostEqual(
                entry["amount"], item.widget_amount, places=2,
                msg=f"Monto que ofrece el widget de {invoice.name} frente a la vista previa")
            self.assertEqual(str(entry["date_to_convert"]), str(item.conversion_date))
            before = invoice.amount_residual
            invoice.js_assign_outstanding_line(origin.id)
            invoice.invalidate_recordset()
            self.assertAlmostEqual(before - invoice.amount_residual, item.apply_amount, places=2)
        self.assertAlmostEqual(abs(origin.amount_residual_currency), item.origin_remaining, places=2)

    def _reverse(self, wizard):
        """Invierte el orden como lo haría el arrastre y deja que el onchange recalcule la vista previa."""
        items = wizard.item_ids.sorted("sequence")
        for item, sequence in zip(items, reversed(items.mapped("sequence"))):
            item.sequence = sequence
        wizard._onchange_item_ids()

    def test_bolivar_payment_follows_the_widget_rule_of_each_invoice_in_both_orders(self):
        """Pago de 6.880 Bs del 01/01 contra una factura de 100 USD del 01/01 (se convierte a la tasa 40) y
        otra de 80 USD del 01/08 (la fecha de conversión es la más reciente, tasa 36): cada factura ofrece
        el pago con su propia regla y el segundo monto sale del residual que dejó el primero."""
        for reverse in (False, True):
            first = self._invoice("2026-01-01", 100.0, self.usd)
            second = self._invoice("2026-08-01", 80.0, self.usd)
            payment = self._outstanding_line(self.bank["VEF"], 6880.0, self.vef, "2026-01-01")
            wizard = self._open_assistant(self._lines(first + second, payment))
            if reverse:
                self._reverse(wizard)
            rows = wizard.item_ids.sorted("sequence")
            expected = {first: ("2026-01-01", 40.0), second: ("2026-08-01", 36.0)}
            for row in rows:
                self.assertEqual(str(row.conversion_date), expected[row.invoice_id][0])
                self.assertAlmostEqual(row.rate, expected[row.invoice_id][1], places=4)
            self._apply_checking_the_real_widget(wizard)
            self.assertTrue(payment.reconciled)
            self.assertTrue(first.payment_state == second.payment_state == "paid")

    def test_dollar_payment_against_bolivar_invoices_follows_each_conversion_date(self):
        """Pago de 100 USD contra facturas en Bs del 01/01 (1.600 Bs, tasa 40) y del 01/08 (2.160 Bs, tasa
        36): se consumen 40 y 60 USD, es decir, cada factura convierte el pago a la tasa de su fecha."""
        first = self._invoice("2026-01-01", 1600.0)
        second = self._invoice("2026-08-01", 2160.0)
        payment = self._outstanding_line(self.bank["USD"], 100.0, self.usd, "2026-01-01")
        wizard = self._open_assistant(self._lines(first + second, payment))
        rows = wizard.item_ids.sorted("sequence")
        self.assertAlmostEqual(rows[0].widget_amount, 4000.0, places=2)
        self.assertAlmostEqual(rows[0].origin_remaining, 60.0, places=2)
        self.assertAlmostEqual(rows[1].widget_amount, 2160.0, places=2)
        self._apply_checking_the_real_widget(wizard)
        self.assertTrue(payment.reconciled)

    def test_keeping_the_value_makes_every_invoice_convert_at_the_payment_date(self):
        """Pago de 4.000 Bs del 01/01 que mantiene el valor: ambas facturas lo convierten a la tasa 40 (la
        del pago) aunque la segunda sea del 01/08, y el reparto es 100 USD en total."""
        first = self._invoice("2026-01-01", 60.0, self.usd)
        second = self._invoice("2026-08-01", 40.0, self.usd)
        payment = self._vef_payment(4000.0, "2026-01-01", keep=True)
        wizard = self._open_assistant(self._lines(first + second, payment))
        rows = wizard.item_ids.sorted("sequence")
        self.assertEqual([str(row.conversion_date) for row in rows], ["2026-01-01", "2026-01-01"])
        self._apply_checking_the_real_widget(wizard)
        self.assertTrue(payment.reconciled)

    def test_third_currency_payment_follows_the_widget_rule(self):
        """Pago en EUR (tasa 50 el 01/01, 45 el 01/08) contra facturas en USD: la conversión pasa por la
        moneda de la compañía y cada fila usa la fecha más reciente entre pago y factura."""
        first = self._invoice("2026-01-01", 50.0, self.usd)
        second = self._invoice("2026-08-01", 40.0, self.usd)
        payment = self._outstanding_line(self.bank["EUR"], 100.0, self.eur, "2026-01-01")
        wizard = self._open_assistant(self._lines(first + second, payment))
        self.assertAlmostEqual(wizard.item_ids.sorted("sequence")[0].widget_amount, 125.0, places=2)
        self.assertGreater(wizard.item_ids.sorted("sequence")[-1].origin_remaining, 0.0,
                           "100 EUR no caben en las dos facturas: el pago conserva saldo, como en el widget")
        self._apply_checking_the_real_widget(wizard)


@tagged("l10n_ve_reconcile_assistant", "-at_install", "post_install")
class TestAssistantUserFlows(ReconcileAssistantCommon):
    """Flujos del usuario con el formulario del asistente: lo que ve al abrirlo, el valor en divisa del pago
    y la compañía activa distinta a la de la factura."""

    def _lines(self, invoices, origin):
        return sum((self._receivable_line(invoice) for invoice in invoices), origin)

    def test_form_shows_the_case_the_origin_and_one_row_per_invoice(self):
        first = self._invoice("2026-08-01", 100.0, self.usd)
        second = self._invoice("2026-08-01", 80.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 6000.0, self.vef, "2026-08-01")
        action = self._lines(first + second, payment).action_l10n_ve_reconcile_assistant()
        with Form.from_action(self.env, action) as form:
            self.assertEqual(form.case, "payment")
            self.assertEqual(form.scenario_label, "1 payment against 2 invoices")
            self.assertEqual(len(form.origin_line_ids), 1)
            self.assertEqual(len(form.invoice_line_ids), 2)
            self.assertEqual(len(form.item_ids), 2)
            self.assertTrue(form.pending_warning)

    def test_form_of_a_blocked_selection_shows_only_the_reason(self):
        advance = self._advance_payment(self.bank["USD"], 100.0)
        payment = self._outstanding_line(self.bank["VEF"], 100.0, self.vef, "2026-08-01")
        with Form.from_action(self.env, (advance + payment).action_l10n_ve_reconcile_assistant()) as form:
            self.assertEqual(form.case, "blocked")
            self.assertIn("against an invoice", form.blocked_reason)
            self.assertEqual(len(form.item_ids), 0)

    def test_keep_value_converts_at_the_payment_date_and_not_keep_at_the_latest(self):
        """Pago en Bs de enero (tasa 40) contra factura en USD de agosto (tasa 36): con "mantener valor" se
        convierte a la fecha del pago (100 USD); sin él, a la fecha más reciente (111,11 USD)."""
        invoice = self._invoice("2026-08-01", 200.0, self.usd)
        kept = self._vef_payment(4000.0, "2026-01-01", keep=True)
        not_kept = self._vef_payment(4000.0, "2026-01-01", keep=False)
        self.assertTrue(kept.payment_id.keep_alter_value_vef)
        self.assertFalse(not_kept.payment_id.keep_alter_value_vef)
        kept_wizard = self._open_assistant(self._lines(invoice, kept))
        self.assertIn("Keeps the value", kept_wizard.item_ids.origin_conditions)
        self.assertEqual(str(kept_wizard.item_ids.conversion_date), "2026-01-01")
        self.assertAlmostEqual(kept_wizard.item_ids.rate, 40.0, places=4)
        self.assertAlmostEqual(kept_wizard.item_ids.widget_amount, 100.0, places=2)
        other_wizard = self._open_assistant(self._lines(invoice, not_kept))
        self.assertNotIn("Keeps the value", other_wizard.item_ids.origin_conditions)
        self.assertEqual(str(other_wizard.item_ids.conversion_date), "2026-08-01")
        self.assertAlmostEqual(other_wizard.item_ids.rate, 36.0, places=4)
        self.assertAlmostEqual(other_wizard.item_ids.widget_amount, 111.11, places=2)
        before = invoice.amount_residual
        kept_wizard.action_confirm()
        self.assertAlmostEqual(before - invoice.amount_residual, 100.0, places=2)

    def test_advance_cross_uses_the_invoice_company_when_another_company_is_active(self):
        """El usuario concilia con otra compañía activa (sin diario de cruces ni cuentas de IGTF propios):
        el cruce de anticipo debe salir en la compañía de la factura, con su diario y su cuenta de IGTF."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        advance = self._advance_payment(self.bank["USD"], 170.0)
        other_company = self.env["res.company"].create({"name": "Compañía activa Prueba Asistente"})
        before = self.env["account.move"].search([("is_advance_move", "=", True)])
        with self._active_company(other_company):
            self.assertEqual(self.env.company, other_company)
            wizard = self._open_assistant(self._lines(invoice, advance).with_env(self.env))
            self.assertEqual(wizard.case, "advance")
            wizard.action_confirm()
        cross = self.env["account.move"].search([("is_advance_move", "=", True)]) - before
        self.assertEqual(len(cross), 1)
        self.assertEqual(cross.company_id, self.company)
        self.assertEqual(cross.journal_id, self.cross_journal)
        self.assertIn(self.igtf_account, cross.line_ids.account_id)
        self.assertEqual(invoice.payment_state, "paid")


@tagged("l10n_ve_reconcile_assistant", "-at_install", "post_install")
class TestAssistantAccess(ReconcileAssistantCommon):
    """Las pruebas corren como superusuario y no ven los permisos de acceso: el asistente debe poder usarlo
    una persona real del grupo de contabilidad, y nadie sin él."""

    def _user(self, group):
        return self.env["res.users"].with_context(no_reset_password=True).create({
            "name": f"Usuario {group}", "login": f"usuario_{group.split('.')[-1]}",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "group_ids": [Command.set([self.env.ref("base.group_user").id, self.env.ref(group).id])],
        })

    def test_an_accountant_opens_and_confirms_the_assistant_with_the_form(self):
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        payment = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-08-01")
        user = self._user("account.group_account_user")
        lines = (self._receivable_line(invoice) + payment).with_user(user)
        with Form.from_action(self.env(user=user), lines.action_l10n_ve_reconcile_assistant()) as form:
            self.assertEqual(form.case, "payment")
            self.assertEqual(len(form.item_ids), 1)
        form.save().action_confirm()
        self.assertEqual(invoice.payment_state, "paid")

    def test_a_user_without_accounting_access_cannot_use_the_assistant(self):
        user = self._user("base.group_user")
        with self.assertRaises(AccessError):
            self.env["l10n_ve.reconcile.assistant"].with_user(user).check_access("read")
