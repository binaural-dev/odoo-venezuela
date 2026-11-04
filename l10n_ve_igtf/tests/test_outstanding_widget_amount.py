from odoo import Command
from odoo.tests import tagged

from .common_currency import CurrencyFixtureCommon


@tagged("l10n_ve_igtf", "-at_install", "post_install")
class TestOutstandingWidgetAmount(CurrencyFixtureCommon):
    """Al asignar un crédito desde el widget, lo aplicado (en moneda de la factura) debe ser lo que mostró.
    El widget valora con `max(invoice_date, line.date)`; el core, con la fecha del pago (línea en moneda
    de la compañía) o el balance en Bs (tercera moneda). Las tasas hacen que difieran, así el test falla
    si el cruce no respeta el widget. Tasas y moneda base: ver `CurrencyFixtureCommon`."""

    def _shown_and_applied(self, invoice, line, **context):
        """Monto del widget para `line` y lo que bajó el residual de `invoice`
        (ambos en la moneda de la factura) tras asignarla desde el widget."""
        invoice.invalidate_recordset(["invoice_outstanding_credits_debits_widget"])
        widget = invoice.invoice_outstanding_credits_debits_widget
        entry = next(c for c in widget["content"] if c["id"] == line.id)
        residual_before = invoice.amount_residual
        invoice.with_context(**context).js_assign_outstanding_line(line.id)
        return entry["amount"], residual_before - invoice.amount_residual


    def test_vef_payment_on_usd_invoice(self):
        """Pago en VEF anterior a la factura en USD: el widget lo valora a la
        tasa de la factura (36), el motor del core a la de la fecha del pago
        (40)."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 100.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)

    def test_usd_payment_on_vef_invoice(self):
        """Pago en USD anterior a la factura en VEF."""
        invoice = self._invoice("2026-08-01", 4000.0)
        line = self._outstanding_line(self.bank["USD"], 80.0, self.usd, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 80.0 * 36.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)

    def test_usd_payment_exceeding_vef_invoice_leaves_payment_balance(self):
        """El pago (USD) vale más de lo que cubre la factura en VEF: se aplica
        solo lo de la factura y el resto del pago queda disponible."""
        invoice = self._invoice("2026-08-01", 4000.0)
        line = self._outstanding_line(self.bank["USD"], 200.0, self.usd, "2026-01-01")
        _shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(applied, 4000.0, places=2)
        self.assertTrue(self.vef.is_zero(invoice.amount_residual))
        self.assertFalse(self.usd.is_zero(line.amount_residual_currency))


    def test_eur_payment_on_usd_invoice(self):
        """Pago en una tercera moneda (EUR) contra factura en USD: 72 EUR x 45 / 36 = 90 USD.
        El pago se consume completo, en EUR y en Bs."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["EUR"], 72.0, self.eur, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 90.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self.assertTrue(self.eur.is_zero(line.amount_residual_currency))
        self.assertTrue(self.vef.is_zero(line.amount_residual))

    def test_eur_payment_exceeding_usd_invoice_is_consumed_partially(self):
        """Pago en EUR que vale más que la factura (consumo parcial): 200 EUR x 45 / 36 = 250 USD
        mostrados, se aplican 100 (80 EUR) y sobran 120 EUR = 6.000 Bs, consistente con su tasa contable (50)."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["EUR"], 200.0, self.eur, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 250.0, places=2)
        self.assertAlmostEqual(applied, 100.0, places=2)
        self.assertTrue(self.usd.is_zero(invoice.amount_residual))
        self.assertAlmostEqual(line.amount_residual_currency, -120.0, places=2)
        self.assertAlmostEqual(line.amount_residual, -6000.0, places=2)

    def test_jpy_payment_on_usd_invoice_zero_decimals(self):
        """Tercera moneda sin decimales (JPY) contra factura en USD: 13333 JPY x 0,25 / 36 = 92,59 USD."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["JPY"], 13333.0, self.jpy, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 92.59, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self.assertTrue(self.jpy.is_zero(line.amount_residual_currency))

    def test_jpy_payment_exceeding_usd_invoice_zero_decimals_partial(self):
        """Consumo parcial de un pago en JPY (0 decimales): 100 USD x 36 = 3.600 Bs = 14.400 JPY.
        El residual en JPY y en Bs queda del mismo lado (nunca JPY agotado con Bs pendientes)."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["JPY"], 20000.0, self.jpy, "2026-01-01")
        _shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(applied, 100.0, places=2)
        self.assertAlmostEqual(line.amount_residual_currency, -(20000.0 - 14400.0), places=0)
        self.assertLess(line.amount_residual, 0.0)

    def test_kwd_payment_on_usd_invoice_three_decimals(self):
        """Tercera moneda con 3 decimales (KWD) contra factura en USD: 27,692 KWD x 120 / 36 = 92,31 USD."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["KWD"], 27.692, self.kwd, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 92.31, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self.assertTrue(self.kwd.is_zero(line.amount_residual_currency))


    def test_jpy_payment_on_vef_invoice_zero_decimals(self):
        """Factura en VEF pagada con JPY (0 decimales): 4.000 Bs / 0,25 (tasa de la factura) = 16.000 JPY."""
        invoice = self._invoice("2026-08-01", 4000.0)
        line = self._outstanding_line(self.bank["JPY"], 16000.0, self.jpy, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 4000.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self.assertTrue(self.jpy.is_zero(line.amount_residual_currency))

    def test_jpy_payment_exceeding_vef_invoice_zero_decimals_partial(self):
        """Pago de 20.000 JPY sobre una factura de 4.000 Bs (16.000 JPY): se aplica solo lo de la factura y el
        residual en JPY y en Bs queda del mismo lado (nunca JPY agotado con Bs pendientes, ni al revés)."""
        invoice = self._invoice("2026-08-01", 4000.0)
        line = self._outstanding_line(self.bank["JPY"], 20000.0, self.jpy, "2026-01-01")
        _shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(applied, 4000.0, places=2)
        self.assertTrue(self.vef.is_zero(invoice.amount_residual))
        self.assertAlmostEqual(line.amount_residual_currency, -4000.0, places=0)
        self.assertLess(line.amount_residual, 0.0)
        # El remanente en Bs sigue a la tasa contable del pago (01-01: 0,27 Bs/JPY): 4.000 JPY x 0,27.
        self.assertAlmostEqual(line.amount_residual, -4000.0 * 0.27, delta=1.0)

    def test_kwd_payment_on_vef_invoice_three_decimals(self):
        """Factura en VEF pagada con KWD (3 decimales): 4.000 Bs / 120 = 33,333 KWD; de un pago de 40 KWD
        sobran 6,667 KWD y los Bs correspondientes, del mismo lado."""
        invoice = self._invoice("2026-08-01", 4000.0)
        line = self._outstanding_line(self.bank["KWD"], 40.0, self.kwd, "2026-01-01")
        _shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(applied, 4000.0, places=2)
        self.assertTrue(self.vef.is_zero(invoice.amount_residual))
        self.assertAlmostEqual(line.amount_residual_currency, -6.667, places=2)
        self.assertLess(line.amount_residual, 0.0)
        # El remanente en Bs sigue a la tasa contable del pago (01-01: 130 Bs/KWD): 6,667 KWD x 130.
        self.assertAlmostEqual(line.amount_residual, -6.667 * 130.0, delta=1.0)

    def test_vendor_bill_with_payment_in_company_currency(self):
        """Factura de PROVEEDOR en USD pagada en VEF (el pago queda del lado
        débito): también debe aplicarse lo mostrado."""
        bill = self._invoice("2026-08-01", 100.0, self.usd, move_type="in_invoice")
        line = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-01-01", "outbound")
        shown, applied = self._shown_and_applied(bill, line)
        self.assertAlmostEqual(shown, 100.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)

    def test_vendor_bill_with_payment_in_third_currency(self):
        bill = self._invoice("2026-08-01", 100.0, self.usd, move_type="in_invoice")
        line = self._outstanding_line(self.bank["EUR"], 72.0, self.eur, "2026-01-01", "outbound")
        shown, applied = self._shown_and_applied(bill, line)
        self.assertAlmostEqual(shown, 90.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)

    def _two_installments_term(self):
        return self.env["account.payment.term"].create({
            "name": "50/50 Prueba Widget",
            "line_ids": [
                Command.create({"value": "percent", "value_amount": 50.0, "delay_type": "days_after", "nb_days": 0}),
                Command.create({"value": "percent", "value_amount": 50.0, "delay_type": "days_after", "nb_days": 30}),
            ],
        })

    def test_invoice_with_two_installments_and_vef_payment(self):
        """Factura en USD con dos cuotas y un pago en VEF: un mismo cruce reparte el pago entre las cuotas
        y lo aplicado es lo mostrado. Además `compute_bi_igtf` no debe reventar (`Expected singleton`)."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd, term=self._two_installments_term())
        line = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 100.0, places=2)
        self.assertAlmostEqual(applied, shown, places=2)
        self.assertGreaterEqual(invoice.bi_igtf, 0.0)

    def test_vef_invoice_with_two_installments_and_usd_payment(self):
        """Factura en VEF con dos cuotas pagada con USD. Con varias cuotas cada parcial redondea a centavos
        (55,56 USD por 2.000 Bs), por eso la tolerancia de 0,5 Bs. Antes `compute_bi_igtf` reventaba
        con `Expected singleton` al asumir una sola línea por cobrar."""
        invoice = self._invoice("2026-08-01", 4000.0, term=self._two_installments_term())
        line = self._outstanding_line(self.bank["USD"], 80.0, self.usd, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 80.0 * 36.0, places=2)
        self.assertAlmostEqual(applied, shown, delta=0.5)
        self.assertGreaterEqual(invoice.bi_igtf, 0.0)

    def test_eur_payment_on_usd_invoice_with_two_installments(self):
        """Tercera moneda con dos cuotas: el pago en EUR se reparte entre ellas en un mismo cruce;
        lo aplicado es lo mostrado y el EUR del pago queda consumido de forma consistente."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd, term=self._two_installments_term())
        line = self._outstanding_line(self.bank["EUR"], 72.0, self.eur, "2026-01-01")
        shown, applied = self._shown_and_applied(invoice, line)
        self.assertAlmostEqual(shown, 90.0, places=2)
        self.assertAlmostEqual(applied, shown, delta=0.02)
        self.assertTrue(self.eur.is_zero(line.amount_residual_currency))
        self.assertTrue(self.vef.is_zero(line.amount_residual))

    def test_retention_reconciliation_keeps_native_rate(self):
        """Los cruces de retenciones (`l10n_ve_exchange_is_retention_reconcile`) no se ajustan al widget:
        conservan la tasa de la fecha del pago (3.600 Bs / 40 = 90 USD, no los 100 que muestra el widget)."""
        invoice = self._invoice("2026-08-01", 100.0, self.usd)
        line = self._outstanding_line(self.bank["VEF"], 3600.0, self.vef, "2026-01-01")
        shown, applied = self._shown_and_applied(
            invoice, line, l10n_ve_exchange_is_retention_reconcile=True,
        )
        self.assertAlmostEqual(shown, 100.0, places=2)
        self.assertAlmostEqual(applied, 90.0, places=2)
