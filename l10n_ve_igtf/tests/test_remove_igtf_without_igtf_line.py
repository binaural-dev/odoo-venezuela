from odoo.tests import tagged

from .common_currency import CurrencyFixtureCommon


@tagged("l10n_ve_igtf", "-at_install", "post_install")
class TestRemoveIgtfWithoutIgtfLine(CurrencyFixtureCommon):
    """`remove_igtf_from_account_move` solo actúa si el asiento del pago lleva línea de IGTF (o es una
    reaplicación de anticipos); en cualquier otro (VEF, diario sin IGTF, modo 'debit_note') se desvía antes.
    Pasarlo a borrador no es inocuo: `button_draft` desconcilia TODAS las líneas del asiento y luego se
    volvía a publicar sin cambios, dejando sin ejecutar el desconciliado normal del parcial."""

    def _pay_two_invoices(self, journal, currency, amount_per_invoice):
        """Un pago que salda DOS facturas de 100 (dos parciales sobre el mismo
        asiento del pago). Devuelve (factura 1, factura 2, asiento del pago)."""
        invoice_1 = self._invoice("2026-08-01", 100.0, self.usd)
        invoice_2 = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(journal, amount_per_invoice * 2, currency, "2026-08-01")
        invoice_1.js_assign_outstanding_line(line.id)
        invoice_2.js_assign_outstanding_line(line.id)
        self.assertEqual(invoice_1.payment_state, "paid")
        self.assertEqual(invoice_2.payment_state, "paid")
        return invoice_1, invoice_2, line.move_id

    def _partials(self, payment_move):
        lines = payment_move.line_ids
        return lines.matched_debit_ids | lines.matched_credit_ids

    def test_usd_payment_without_igtf_line_is_not_touched(self):
        invoice_1, invoice_2, payment_move = self._pay_two_invoices(self.bank["USD"], self.usd, 100.0)
        partials = self._partials(payment_move)
        self.assertEqual(len(partials), 2)
        partial_1 = partials.filtered(lambda p: invoice_1.line_ids & (p.debit_move_id | p.credit_move_id))

        result = invoice_1.remove_igtf_from_account_move(partial_1.id)

        self.assertFalse(result, "Sin línea de IGTF no hay nada que quitar")
        self.assertEqual(payment_move.state, "posted", "El pago no debe pasar a borrador")
        self.assertEqual(len(self._partials(payment_move)), 2, "No debe desconciliar ningún parcial")

    def test_vef_payment_is_not_touched(self):
        """Pago en VEF: sale por la salida anticipada ya existente (VEF sin cruce de anticipo), no por la rama
        de "sin línea de IGTF"; esa la cubre el test del pago en USD. Se conserva como regresión."""
        invoice_1, invoice_2, payment_move = self._pay_two_invoices(self.bank["VEF"], self.vef, 3600.0)
        partials = self._partials(payment_move)
        partial_1 = partials.filtered(lambda p: invoice_1.line_ids & (p.debit_move_id | p.credit_move_id))

        self.assertFalse(invoice_1.remove_igtf_from_account_move(partial_1.id))

        self.assertEqual(payment_move.state, "posted")
        self.assertEqual(len(self._partials(payment_move)), len(partials))

    def test_unreconciling_one_partial_keeps_the_other_invoice_paid(self):
        """De punta a punta, con el botón del widget: al desconciliar UNA factura
        la otra sigue pagada con su parcial intacto."""
        invoice_1, invoice_2, payment_move = self._pay_two_invoices(self.bank["USD"], self.usd, 100.0)
        partials = self._partials(payment_move)
        partial_1 = partials.filtered(lambda p: invoice_1.line_ids & (p.debit_move_id | p.credit_move_id))

        invoice_1.js_remove_outstanding_partial(partial_1.id)

        self.assertEqual(payment_move.state, "posted")
        self.assertEqual(invoice_1.payment_state, "not_paid")
        self.assertEqual(invoice_2.payment_state, "paid", "La otra factura debía seguir pagada")
        self.assertEqual(len(self._partials(payment_move)), 1)
