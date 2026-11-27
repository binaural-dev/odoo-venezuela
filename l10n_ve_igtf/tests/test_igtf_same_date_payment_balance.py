import logging
from datetime import timedelta

from odoo import Command
from odoo.tests import Form, tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments

_logger = logging.getLogger(__name__)

USD_RATE = 855.6625
EUR_RATE = 976.900911
# Con IVA 16 % excluido la línea es 862,07 (+ IVA = USD 1.000,00: la base
# redondeada del caso VEN-E01); con IVA incluido el precio es 1.000.
PRICE = {"excl": 862.07, "incl": 1000.0}
PRICE_VEF = {"excl": 100000.0, "incl": 116000.0}
ROUNDING_METHODS = ("round_per_line", "round_globally")


@tagged("post_install", "-at_install", "l10n_ve_igtf_same_date_balance")
class TestIgtfSameDatePaymentBalance(TestIndexedPayments):
    """Pagos del wizard hechos el MISMO día de la factura.

    Con la factura y el pago en la misma fecha los Bs. del pago deben ser los
    de la factura: si el pago cubre la deuda (completo, o con una diferencia
    mínima conciliada contra una cuenta de ajuste, o el último de varios
    pagos) la factura queda pagada y NO nace nota ni asiento de diferencial
    cambiario. Se cubren facturas y pagos en Bs., USD y EUR, con y sin IGTF,
    con y sin write-off, en ventas y compras. Todo se opera con ``Form``
    (factura, línea y wizard).

    El problema se detectó en la matriz de casos de diferencial cambiario
    (COM-E01 / VEN-E01 y los casos con IVA): depende de cómo se calculan los
    impuestos, así que la matriz se repite con el redondeo por línea y global
    y con el IVA incluido y excluido. Además se comprueba que con fechas
    distintas (A04, A05 de la matriz) el diferencial real se sigue generando.
    """

    def setUp(self):
        super().setUp()
        self.company.igtf_percentage = 3.0
        self.company.taxpayer_type = "special"
        self.invoice_date = self.payment_date
        self._set_rate(self.currency_usd, self.payment_date, USD_RATE)
        self._set_rate(self.currency_eur, self.payment_date, EUR_RATE)

        mk = self.env["account.account"].create
        self.account_payable = mk({
            "name": "Payable", "code": "210000", "account_type": "liability_payable",
            "company_ids": [(6, 0, [self.company.id])], "reconcile": True,
        })
        self.account_expense = mk({
            "name": "Expense", "code": "500000", "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.account_writeoff = mk({
            "name": "Ajuste de pago", "code": "590000", "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        igtf_customer = mk({
            "name": "IGTF Customer", "code": "236000", "account_type": "liability_current",
            "company_ids": [(6, 0, [self.company.id])],
        })
        igtf_supplier = mk({
            "name": "IGTF Supplier", "code": "510000", "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.company.write({
            "customer_account_igtf_id": igtf_customer.id,
            "supplier_account_igtf_id": igtf_supplier.id,
        })
        self.partner.write({
            "property_account_payable_id": self.account_payable.id,
            "default_advance_customer_account_id": igtf_customer.id,
            "default_advance_supplier_account_id": igtf_supplier.id,
            "taxpayer_type": "special",
        })
        self.purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchase Test", "code": "PRTST", "type": "purchase",
            "company_id": self.company.id, "default_account_id": self.account_expense.id,
        })
        self.products = {}
        for mode, included in (("excl", False), ("incl", True)):
            sale_vat = self._make_vat("sale", included)
            purchase_vat = self._make_vat("purchase", included)
            self.products[mode] = self.env["product.product"].create({
                "name": f"Servicio IVA {mode}", "type": "service", "list_price": 100.0,
                "taxes_id": [(6, 0, [sale_vat.id])],
                "supplier_taxes_id": [(6, 0, [purchase_vat.id])],
            })

        self.journals = {
            "VEF": self._bank("BVEF", self.currency_vef),
            "USD": self._bank("BUSD", self.currency_usd),
            "EUR": self._bank("BEUR", self.currency_eur),
            "USD-IGTF": self._bank("BUSDI", self.currency_usd, is_igtf=True),
            "EUR-IGTF": self._bank("BEURI", self.currency_eur, is_igtf=True),
        }

    # -- fixtures -------------------------------------------------------------

    def _make_vat(self, use, included=False):
        vals = {
            "name": f"IVA 16% {use} {'incl' if included else 'excl'}", "amount": 16.0,
            "amount_type": "percent", "type_tax_use": use, "company_id": self.company.id,
            "tax_group_id": self.test_tax_group.id,
        }
        if included:
            if "price_include_override" in self.env["account.tax"]._fields:
                vals["price_include_override"] = "tax_included"
            else:
                vals["price_include"] = True
        return self.env["account.tax"].create(vals)

    def _bank(self, code, currency, is_igtf=False):
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        return self.env["account.journal"].sudo().create({
            "name": f"Bank {code}", "type": "bank", "code": code,
            "currency_id": currency.id, "is_igtf": is_igtf,
            "company_id": self.company.id, "default_account_id": self.account_bank.id,
            "inbound_payment_method_line_ids": [Command.create({
                "name": f"In {code}", "payment_method_id": manual_in.id,
                "payment_account_id": self.account_bank.id,
            })],
            "outbound_payment_method_line_ids": [Command.create({
                "name": f"Out {code}", "payment_method_id": manual_out.id,
                "payment_account_id": self.account_bank.id,
            })],
        })

    def _document(self, side, currency, mode="excl", invoice_date=None):
        """Factura de venta/compra creada con Form como en pantalla: cabecera
        y una línea de producto con IVA 16 % incluido (precio 1.000) o excluido
        (línea 862,07; Bs. 100.000 + IVA en Bs.)."""
        sale = side == "ven"
        date = invoice_date or self.invoice_date
        price = (PRICE_VEF if currency == self.currency_vef else PRICE)[mode]
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice" if sale else "in_invoice",
        )) as form:
            form.partner_id = self.partner
            form.journal_id = self.sale_journal if sale else self.purchase_journal
            form.invoice_date_display = date
            form.invoice_date = date
            form.currency_id = currency
            if not sale:
                form.ref = f"BILL-{date}"
        move = form.save()
        with Form(move) as line_form:
            with line_form.invoice_line_ids.new() as line:
                line.product_id = self.products[mode]
                line.quantity = 1
                line.price_unit = price
        move = line_form.save()
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _wizard(self, invoice, journal, currency, amount=None, delta=None, writeoff=False):
        """Abre el wizard como en pantalla: diario, moneda, fecha y, si se
        pide, un monto (o la propuesta + `delta`) y la diferencia conciliada."""
        with Form.from_action(self.env, invoice.action_register_payment()) as form:
            form.journal_id = journal
            form.save()
            form.currency_id = currency
            form.save()
            form.payment_date = self.payment_date
            form.save()
            proposed = form.amount
            if amount is not None:
                form.amount = amount
                form.save()
            elif delta:
                form.amount = proposed + delta
                form.save()
            if writeoff:
                form.payment_difference_handling = "reconcile"
                form.writeoff_account_id = self.account_writeoff
                form.save()
        return form.record, proposed

    def _pay(self, invoice, journal_key, cur, **kwargs):
        wizard, proposed = self._wizard(invoice, self.journals[journal_key], cur, **kwargs)
        payments = wizard._create_payments()
        return payments, proposed

    def _notes_and_exchange(self, invoice):
        ar = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
        )
        partials = ar.matched_debit_ids | ar.matched_credit_ids
        exch = partials.mapped("exchange_move_id")
        notes = self.env["account.move"]
        if "l10n_ve_exchange_source_move_id" in self.env["account.move"]._fields:
            notes = self.env["account.move"].search([("l10n_ve_exchange_source_move_id", "=", invoice.id)])
        return exch, notes

    def _check_closed(self, invoice):
        """La factura queda pagada y sin nota ni asiento de diferencial."""
        self.assertIn(invoice.payment_state, ("paid", "in_payment"), "La factura debe quedar pagada.")
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual_signed) or invoice.company_currency_id.is_zero(invoice.amount_residual),
                        f"Saldo de la factura: {invoice.amount_residual} Bs.")
        exch, notes = self._notes_and_exchange(invoice)
        self.assertFalse(exch, "Asiento de diferencial: %s" % [
            (m.name, m.date, [(l.account_id.code, round(l.debit, 2), round(l.credit, 2),
                               round(l.foreign_debit, 2), round(l.foreign_credit, 2)) for l in m.line_ids])
            for m in exch])
        self.assertFalse(notes, f"ND/NC de diferencial: {[(m.name, m.amount_total) for m in notes]}")

    # -- matriz ---------------------------------------------------------------
    # cada caso: (id, moneda de la factura, diario de pago, moneda del pago, modo)
    # modo: full | writeoff | partial2 (primero 40 %, luego lo propuesto)
    CASES = [
        # sin IGTF, pago completo
        ("USD>USD", "USD", "USD", "USD", "full"),
        ("USD>Bs", "USD", "VEF", "VEF", "full"),
        ("Bs>USD", "VEF", "USD", "USD", "full"),
        ("USD>EUR", "USD", "EUR", "EUR", "full"),
        ("EUR>USD", "EUR", "USD", "USD", "full"),
        ("EUR>EUR", "EUR", "EUR", "EUR", "full"),
        ("EUR>Bs", "EUR", "VEF", "VEF", "full"),
        # con IGTF, pago completo
        ("USD>USD-IGTF", "USD", "USD-IGTF", "USD", "full"),
        ("Bs>USD-IGTF", "VEF", "USD-IGTF", "USD", "full"),
        ("USD>EUR-IGTF", "USD", "EUR-IGTF", "EUR", "full"),
        ("EUR>USD-IGTF", "EUR", "USD-IGTF", "USD", "full"),
        # write-off: diferencia mínima conciliada contra una cuenta de ajuste
        ("USD>USD w/o", "USD", "USD", "USD", "writeoff"),
        ("USD>Bs w/o", "USD", "VEF", "VEF", "writeoff"),
        ("Bs>USD w/o", "VEF", "USD", "USD", "writeoff"),
        ("USD>EUR w/o", "USD", "EUR", "EUR", "writeoff"),
        ("USD>USD-IGTF w/o", "USD", "USD-IGTF", "USD", "writeoff"),
        ("Bs>USD-IGTF w/o", "VEF", "USD-IGTF", "USD", "writeoff"),
        # dos pagos el mismo día: el último cierra la factura
        ("USD>USD 2pagos", "USD", "USD", "USD", "partial2"),
        ("USD>Bs 2pagos", "USD", "VEF", "VEF", "partial2"),
        ("Bs>USD 2pagos", "VEF", "USD", "USD", "partial2"),
        ("USD>USD-IGTF 2pagos", "USD", "USD-IGTF", "USD", "partial2"),
    ]
    # diferencia mínima que se concilia en los casos write-off, en la moneda
    # del pago (centavos): el pago queda por debajo de lo propuesto.
    WRITEOFF_DELTA = -0.05

    def _run_case(self, side, case, mode):
        cid, inv_cur, journal_key, pay_cur, kind = case
        cur = {"USD": self.currency_usd, "EUR": self.currency_eur, "VEF": self.currency_vef}
        invoice = self._document(side, cur[inv_cur], mode)
        if kind == "full":
            self._pay(invoice, journal_key, cur[pay_cur])
        elif kind == "writeoff":
            self._pay(invoice, journal_key, cur[pay_cur], delta=self.WRITEOFF_DELTA, writeoff=True)
        else:  # partial2
            _wizard, proposed = self._wizard(invoice, self.journals[journal_key], cur[pay_cur])
            first = cur[pay_cur].round(proposed * 0.4)
            self._pay(invoice, journal_key, cur[pay_cur], amount=first)
            self.assertEqual(invoice.payment_state, "partial")
            self._pay(invoice, journal_key, cur[pay_cur])
        self._check_closed(invoice)

    def _run_matrix(self, side, rounding, mode):
        """Toda la matriz con un método de redondeo de impuestos y con el IVA
        incluido (`incl`) o excluido (`excl`); informa cada caso que falle."""
        self.company.tax_calculation_rounding_method = rounding
        failures = []
        for case in self.CASES:
            label = f"{side.upper()} {rounding} {mode} {case[0]}"
            try:
                with self.env.cr.savepoint():
                    self._run_case(side, case, mode)
                _logger.info("ZZRES|%s|OK", label)
            except Exception as exc:  # noqa: BLE001 - se reporta cada caso
                msg = str(exc).replace("\n", " ")[:600]
                _logger.warning("ZZRES|%s|FAIL|%s", label, msg)
                failures.append(f"{label}: {msg}")
        self.assertFalse(failures, "Casos con falla:\n" + "\n".join(failures))

    # -- una prueba por lado, redondeo e IVA ----------------------------------

    def test_sales_per_line_tax_excluded(self):
        self._run_matrix("ven", "round_per_line", "excl")

    def test_sales_per_line_tax_included(self):
        self._run_matrix("ven", "round_per_line", "incl")

    def test_sales_global_tax_excluded(self):
        self._run_matrix("ven", "round_globally", "excl")

    def test_sales_global_tax_included(self):
        self._run_matrix("ven", "round_globally", "incl")

    def test_purchases_per_line_tax_excluded(self):
        self._run_matrix("com", "round_per_line", "excl")

    def test_purchases_per_line_tax_included(self):
        self._run_matrix("com", "round_per_line", "incl")

    def test_purchases_global_tax_excluded(self):
        self._run_matrix("com", "round_globally", "excl")

    def test_purchases_global_tax_included(self):
        self._run_matrix("com", "round_globally", "incl")

    # -- con fechas distintas el diferencial real se sigue generando ----------

    def _exchange_loss_or_gain(self, invoice):
        exch, _notes = self._notes_and_exchange(invoice)
        return sum(exch.line_ids.mapped("debit"))

    def test_different_date_keeps_real_exchange_difference(self):
        """COM/VEN-A04 y A05 de la matriz: factura USD 1.000 el 25/09 (tasa
        855,6625) pagada el 28/09 (tasa 857,0058) en USD o en Bs. El pago no se
        iguala a los Bs. de la factura: queda el diferencial de Bs. 1.343,30."""
        invoice_date = self.payment_date - timedelta(days=3)
        self._set_rate(self.currency_usd, invoice_date, USD_RATE)
        self._set_rate(self.currency_usd, self.payment_date, 857.0058)
        for side in ("ven", "com"):
            for mode in ("incl", "excl"):
                for journal_key, cur, label in (
                    ("USD", self.currency_usd, "A05 USD>USD"),
                    ("VEF", self.currency_vef, "A04 USD>Bs"),
                ):
                    with self.subTest(side=side, mode=mode, case=label), self.env.cr.savepoint():
                        invoice = self._document(side, self.currency_usd, mode, invoice_date=invoice_date)
                        self._pay(invoice, journal_key, cur)
                        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
                        diff = self._exchange_loss_or_gain(invoice)
                        if mode == "incl":
                            self.assertAlmostEqual(diff, 1343.30, delta=0.05)
                        else:  # las líneas redondeadas suman Bs. 1,03 más
                            self.assertAlmostEqual(diff, 1343.30, delta=1.5)

    # -- IGTF + write-off con fechas distintas (COM/VEN-C04x y C05x) ----------

    def test_igtf_writeoff_different_date_in_company_units(self):
        """COM/VEN-C04x y C05x de la matriz: factura el 25/09 pagada el 28/09
        en otra moneda con diario IGTF y la diferencia mínima conciliada contra
        una cuenta de ajuste. El ajuste del IGTF mezclaba unidades (Bs. contra
        la moneda del pago) y escribía en la cuenta de ajuste el total de la
        factura (en ventas C04x Bs. 856.005,86 en vez de Bs. 1.343,36): la factura quedaba
        parcial en ventas. Ahora el ajuste es la diferencia mínima y la factura
        queda pagada."""
        invoice_date = self.payment_date - timedelta(days=3)
        self._set_rate(self.currency_usd, invoice_date, USD_RATE)
        self._set_rate(self.currency_usd, self.payment_date, 857.0058)
        self._set_rate(self.currency_eur, invoice_date, 972.648677)
        cases = (
            # (caso, moneda factura, monto, diario IGTF, moneda del pago, monto del pago)
            ("C04x USD>EUR-IGTF", self.currency_usd, "EUR-IGTF", self.currency_eur, 903.59),
            ("C05x EUR>USD-IGTF", self.currency_eur, "USD-IGTF", self.currency_usd, 1174.10),
        )
        # Ajuste esperado en Bs. (valor absoluto) por lado y caso. En el código
        # anterior ventas escribía Bs. 856.005,86 (C04x) y Bs. 1.831.906,77 (C05x),
        # compras Bs. 975.900,91 (C04x) y dejaba Bs. 0 con USD 121,04 (C05x).
        expected_writeoff_bs = {
            ("ven", "C04x"): 1343.36, ("ven", "C05x"): 5595.59,
            ("com", "C04x"): 4252.23, ("com", "C05x"): 0.0,
        }
        for side in ("ven", "com"):
            for label, inv_cur, journal_key, pay_cur, amount in cases:
                with self.subTest(side=side, case=label), self.env.cr.savepoint():
                    self.company.tax_calculation_rounding_method = "round_globally"
                    invoice = self._document(side, inv_cur, "incl", invoice_date=invoice_date)
                    self._pay(invoice, journal_key, pay_cur, amount=amount, writeoff=True)
                    self.assertIn(invoice.payment_state, ("paid", "in_payment"),
                                  "La factura debe quedar pagada.")
                    writeoff_lines = self.env["account.move.line"].search([
                        ("account_id", "=", self.account_writeoff.id),
                        ("move_id.state", "=", "posted"),
                    ])
                    self.assertAlmostEqual(
                        abs(sum(writeoff_lines.mapped("balance"))),
                        expected_writeoff_bs[(side, label[:4])], delta=0.05,
                        msg="El ajuste debe ser la diferencia mínima, en Bs.",
                    )
