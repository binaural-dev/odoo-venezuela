from unittest.mock import patch

from odoo import fields
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .test_withholding_common_VEF import RetentionTestCommon

RATE = 771.07


@tagged("post_install", "-at_install", "retention_amount_tolerance")
class TestRetentionAmountTolerance(RetentionTestCommon):
    """`account.move._retention_amount_tolerance` es la mayor diferencia, en
    moneda de compania, entre lo retenido y lo adeudado que sigue siendo
    redondeo entre monedas: la que convertida a la moneda del documento
    redondea a cero. Trabaja solo con montos en moneda de compania; no usa
    los campos alternos (`foreign_*`) de las lineas de retencion."""

    def setUp(self):
        super().setUp()
        hoy = fields.Date.today()
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id), ("name", "=", hoy),
        ]).unlink()
        self.currency_usd.write({"rate_ids": [(0, 0, {
            "name": hoy, "rate": 1 / RATE, "company_rate": 1 / RATE, "inverse_company_rate": RATE,
        })]})
        self.journal_multi = self.Journal.create({
            "name": "Venta multimoneda", "type": "sale", "code": "SVMT", "company_id": self.company.id,
        })

    def _invoice(self, currency, journal, date=None):
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=journal.id,
        )) as form:
            form.partner_id = self.partner_pnr_75
            form.invoice_date = date or fields.Date.today()
            form.currency_id = self.currency_vef
        invoice = form.save()
        with Form(invoice) as form_edit:
            with form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = form_edit.save()
        if currency != self.currency_vef:
            invoice.write({"currency_id": currency.id})
        return invoice

    def test_tolerancia_coincide_con_la_regla_de_redondeo_a_varias_tasas(self):
        """Para cada tasa: una diferencia es tolerable si y solo si, reconvertida a
        la moneda del documento, redondea a cero (la regla del cierre de facturas en
        moneda extranjera), y la tolerancia es el mayor paso de la moneda de
        compania que cumple eso."""
        step = self.company.currency_id.rounding
        rates = {0: 771.07, 1: 772.54, 2: 380.0, 3: 400.0, 4: 1000.13, 5: 55.55}
        for days_ago, rate in rates.items():
            date = fields.Date.subtract(fields.Date.today(), days=days_ago)
            self.env["res.currency.rate"].search([
                ("currency_id", "=", self.currency_usd.id), ("name", "=", date),
            ]).unlink()
            self.currency_usd.write({"rate_ids": [(0, 0, {
                "name": date, "rate": 1 / rate, "company_rate": 1 / rate, "inverse_company_rate": rate,
            })]})
            document = self._invoice(self.currency_usd, self.journal_multi, date=date)
            tolerance = document._retention_amount_tolerance()
            doc_currency = document.currency_id
            # Siempre `_convert()` a la fecha del documento, nunca una tasa multiplicada.
            rounds_to_zero = lambda diff: doc_currency.is_zero(  # noqa: E731
                self.company.currency_id._convert(
                    diff, doc_currency, self.company, document._get_invoice_currency_rate_date(),
                )
            )
            with self.subTest(rate=rate):
                self.assertGreater(tolerance, 0.0)
                self.assertTrue(rounds_to_zero(tolerance))
                self.assertFalse(rounds_to_zero(tolerance + step))
                # El cierre de facturas decide con la misma regla.
                due = abs(document.amount_residual_signed)
                self.assertAlmostEqual(
                    document._retention_difference_within_currency_precision(due + tolerance),
                    tolerance, places=2,
                )
                self.assertIsNone(
                    document._retention_difference_within_currency_precision(due + tolerance + step)
                )
                self.assertAlmostEqual(
                    document._retention_difference_within_currency_precision(due - tolerance),
                    -tolerance, places=2,
                )

    def test_tolerancia_es_cero_en_moneda_de_compania(self):
        document = self._invoice(self.currency_vef, self.sale_journal)
        self.assertEqual(document._retention_amount_tolerance(), 0.0)
        self.assertEqual(document._retention_max_accepted_difference(), 0.0)
        self.assertFalse(document._retention_closes_document_currency_debt(
            abs(document.amount_residual_signed)))
        self.assertIsNone(document._retention_difference_within_currency_precision(
            abs(document.amount_residual_signed) + 0.01))

    def test_tope_aceptado_por_los_portales_es_menor_a_un_centimo_completo(self):
        """El tope que reciben los portales es el mayor paso en moneda de compania
        que, llevado a la moneda del documento con `_convert()`, sigue por debajo de
        un centimo completo; mayor que la tolerancia de medio centimo."""
        step = self.company.currency_id.rounding
        document = self._invoice(self.currency_usd, self.journal_multi)
        doc_currency = document.currency_id
        date = document._get_invoice_currency_rate_date()
        to_document = lambda amount: self.company.currency_id._convert(  # noqa: E731
            amount, doc_currency, self.company, date, round=False)
        top = document._retention_max_accepted_difference()
        self.assertGreater(top, document._retention_amount_tolerance())
        self.assertLess(to_document(top), doc_currency.rounding)
        self.assertGreaterEqual(to_document(top + step), doc_currency.rounding)

    def test_retencion_que_cierra_la_deuda_comercial_en_la_moneda_del_documento(self):
        """Regla 2: aunque la diferencia en VEF supere medio centimo de la divisa, si la
        retencion llevada a la divisa con `_convert()` es igual a la deuda comercial
        (a la precision de la divisa), la diferencia es redondeo."""
        document = self._invoice(self.currency_usd, self.journal_multi)
        company_currency = self.company.currency_id
        doc_currency = document.currency_id
        due = abs(document.amount_residual_signed)
        # Retencion que cierra la deuda en USD pero queda a mas de medio centimo del
        # saldo en VEF: se construye desde la deuda en USD, movida casi medio centimo.
        debt_in_bs = doc_currency._convert(
            document.amount_residual, company_currency, self.company,
            document._get_invoice_currency_rate_date(), round=False,
        )
        half_cent = document._retention_amount_tolerance()
        retention = company_currency.round(debt_in_bs + half_cent * 0.99)
        diff = retention - due
        self.assertTrue(document._retention_closes_document_currency_debt(retention))
        self.assertAlmostEqual(
            document._retention_difference_within_currency_precision(retention), diff, places=2,
        )
        # Un centimo completo mas ya es otra cifra en la divisa: monto real.
        one_cent_more = company_currency.round(debt_in_bs + document._retention_max_accepted_difference() + 1.0)
        self.assertFalse(document._retention_closes_document_currency_debt(one_cent_more))
        self.assertIsNone(document._retention_difference_within_currency_precision(one_cent_more))

    def test_regla_2_respeta_el_tope_aunque_la_deuda_comercial_cierre(self):
        """Rule 2 is capped: even if the retention closes the commercial debt, a
        difference above `_retention_max_accepted_difference()` is a real amount."""
        document = self._invoice(self.currency_usd, self.journal_multi)
        due = abs(document.amount_residual_signed)
        top = document._retention_max_accepted_difference()
        step = self.company.currency_id.rounding
        with patch.object(
            type(document), "_retention_closes_document_currency_debt", return_value=True,
        ):
            self.assertIsNone(
                document._retention_difference_within_currency_precision(due + top + step))
            self.assertIsNone(
                document._retention_difference_within_currency_precision(due - top - step))
            self.assertAlmostEqual(
                document._retention_difference_within_currency_precision(due + top),
                top, places=2,
            )

    def test_limites_toleran_ruido_de_float(self):
        """A difference sitting exactly on a bound is accepted even if the float
        subtraction against the residual adds noise."""
        document = self._invoice(self.currency_usd, self.journal_multi)
        due = abs(document.amount_residual_signed)
        tolerance = document._retention_amount_tolerance()
        noisy = (due + tolerance) + 1e-9
        self.assertIsNotNone(document._retention_difference_within_currency_precision(noisy))

    def test_sin_redondeo_si_la_moneda_de_compania_no_es_bolivar(self):
        """Rounding between currencies only applies to companies whose currency is VEF."""
        document = self._invoice(self.currency_usd, self.journal_multi)
        due = abs(document.amount_residual_signed)
        self.assertIsNotNone(document._retention_difference_within_currency_precision(due + 0.01))
        with patch.object(
            type(self.company.currency_id), "is_venezuelan_bolivar", return_value=False,
        ):
            self.assertIsNone(document._retention_difference_within_currency_precision(due + 0.01))


@tagged("post_install", "-at_install", "retention_iva_amount_single_calculation")
class TestRetentionIvaAmountSingleCalculation(RetentionTestCommon):
    """El monto de la retencion de IVA se calcula en un solo lugar
    (`account.retention.compute_iva_retention_amount`): la carga de lineas, la
    linea de retencion y los portales lo usan; si cambia, todos lo siguen."""

    def _supplier_bill(self, price=1000.0):
        import random
        with Form(self.env["account.move"].with_context(
            default_move_type="in_invoice", default_journal_id=self.purchase_journal.id,
        )) as form:
            form.partner_id = self.partner_pnr_75
            form.invoice_date = fields.Date.today()
            form.currency_id = self.currency_vef
            form.correlative = str(random.randint(10000000000000, 99999999999999))
        bill = form.save()
        with Form(bill) as form_edit:
            with form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = price
        bill = form_edit.save()
        bill.with_context(move_action_post_alert=True).action_post()
        return bill

    def _retention_lines_from_form(self, bill):
        action = self.env.ref("l10n_ve_payment_extension.action_retention_iva_supplier").read()[0]
        ctx = safe_eval(action.get("context", "{}"))
        view = "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension"
        with Form(self.env[action["res_model"]].with_context(ctx), view=view) as form:
            form.partner_id = bill.partner_id
            form.date_accounting = fields.Date.today()
        return form.save().retention_line_ids

    def test_helper_is_the_percentage_of_the_tax_amount_in_absolute_value(self):
        Retention = self.env["account.retention"]
        self.assertEqual(Retention.compute_iva_retention_amount(160.0, 75.0), 120.0)
        self.assertEqual(Retention.compute_iva_retention_amount(-160.0, 75.0), 120.0)
        self.assertEqual(Retention.compute_iva_retention_amount(160.0, 100.0), 160.0)
        self.assertEqual(Retention.compute_iva_retention_amount(0.0, 75.0), 0.0)

    def test_loaded_lines_use_the_helper(self):
        bill = self._supplier_bill(1000.0)
        line = self._retention_lines_from_form(bill)
        self.assertEqual(
            line.retention_amount,
            self.env["account.retention"].compute_iva_retention_amount(line.iva_amount, 75.0),
        )

    def test_a_change_in_the_helper_is_followed_by_the_loaded_lines(self):
        bill = self._supplier_bill(1000.0)
        Retention = type(self.env["account.retention"])
        with patch.object(Retention, "compute_iva_retention_amount",
                          lambda self, tax_amount, pct: abs(tax_amount) * 0.5):
            line = self._retention_lines_from_form(bill)
        self.assertAlmostEqual(line.retention_amount, abs(line.iva_amount) * 0.5, places=2)
