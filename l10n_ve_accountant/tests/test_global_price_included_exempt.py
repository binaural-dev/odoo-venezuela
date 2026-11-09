from odoo import fields
from odoo.tests import Form, TransactionCase, tagged

from .common_rates import set_rate


@tagged("post_install", "-at_install", "l10n_ve_global_included_exempt")
class TestGlobalPriceIncludedExempt(TransactionCase):
    """Con `round_globally`, IVA incluido en el precio y una línea exenta, el
    centavo del redondeo global del núcleo caía en la línea exenta y el IVA
    por línea de `_sync_tax_lines` ya no lo compensaba: el total del asiento
    quedaba 0,01 distinto de lo digitado y el widget no coincidía con el
    asiento ni con el alterno de los apuntes."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        ve = self.env.ref("base.ve")
        self.vef, self.usd, self.eur = (self.env.ref(x) for x in ("base.VEF", "base.USD", "base.EUR"))
        (self.vef | self.usd | self.eur).write({"active": True})
        self.company.write({
            "currency_id": self.vef.id, "foreign_currency_id": self.usd.id,
            "country_id": ve.id, "account_fiscal_country_id": ve.id,
        })
        today = fields.Date.context_today(self.env.user)
        set_rate(self.env, self.vef, today, self.company, 1.0)
        set_rate(self.env, self.usd, today, self.company, 40.0)
        set_rate(self.env, self.eur, today, self.company, 50.0)
        self.today = today

        def account(code, name, account_type, reconcile=False):
            acc = self.env["account.account"].search(
                [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1)
            return acc or self.env["account.account"].create({
                "code": code, "name": name, "account_type": account_type,
                "company_ids": [(6, 0, [self.company.id])], "reconcile": reconcile})

        a_rec = account("991200", "CxC test", "asset_receivable", True)
        self.a_inc = account("994000", "Ingresos test", "income")
        a_tax = account("992000", "IVA test", "liability_current", True)
        group_iva = self.env["account.tax.group"].create(
            {"name": "IVA", "company_id": self.company.id, "country_id": ve.id})
        group_exe = self.env["account.tax.group"].create(
            {"name": "Exento", "company_id": self.company.id, "country_id": ve.id})
        group_extra = self.env["account.tax.group"].create({
            "name": "Adicional", "company_id": self.company.id, "country_id": ve.id,
            "preceding_subtotal": "Subtotal con IVA"})

        def tax(name, amount, included, group):
            def rep():
                return [
                    (0, 0, {"repartition_type": "base", "factor_percent": 100.0}),
                    (0, 0, {"repartition_type": "tax", "factor_percent": 100.0, "account_id": a_tax.id}),
                ]
            return self.env["account.tax"].with_company(self.company).create({
                "name": name, "amount": amount, "amount_type": "percent", "type_tax_use": "sale",
                "price_include_override": "tax_included" if included else "tax_excluded",
                "company_id": self.company.id, "tax_group_id": group.id,
                "invoice_repartition_line_ids": rep(), "refund_repartition_line_ids": rep()})

        self.taxes = {
            "incl": tax("IVA incl test", 16.0, True, group_iva),
            "excl": tax("IVA excl test", 16.0, False, group_iva),
            "exe": tax("Exento test", 0.0, False, group_exe),
            "exei": tax("Exento incluido test", 0.0, True, group_exe),
            "extra": tax("Adicional test", 3.0, False, group_extra),
        }
        self.partner = self.env["res.partner"].create(
            {"name": "Cliente test", "country_id": ve.id, "property_account_receivable_id": a_rec.id})
        self.products = [
            self.env["product.product"].create({
                "name": n, "type": "service", "list_price": 1,
                "property_account_income_id": self.a_inc.id, "taxes_id": [(5, 0, 0)]})
            for n in ("A", "B", "C", "D")
        ]
        self.journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1)

    def _invoice(self, currency, method, lines, modes):
        self.company.tax_calculation_rounding_method = method
        for product, mode in zip(self.products, modes):
            product.taxes_id = [(6, 0, [self.taxes[mode].id])]
        pricelist = self.env["product.pricelist"].search([("currency_id", "=", currency.id)], limit=1) \
            or self.env["product.pricelist"].create({"name": "PL " + currency.name, "currency_id": currency.id})
        form = Form(self.env["account.move"].with_context(default_move_type="out_invoice"))
        form.partner_id = self.partner
        form.currency_id = currency
        form.journal_id = self.journal
        try:
            form.pricelist_id = pricelist
        except Exception:  # noqa: BLE001 - el campo depende de account_invoice_pricelist
            pass
        for product, (price, qty) in zip(self.products, lines):
            with form.invoice_line_ids.new() as line:
                line.product_id = product
                line.quantity = qty
                line.price_unit = price
        move = form.save()
        move.action_post()
        return move

    def _assert_consistent(self, move, expected_total=None, check_lines=True):
        digits = move.currency_id.decimal_places
        for line in move.invoice_line_ids if check_lines else []:
            self.assertAlmostEqual(
                -line.amount_currency, line.price_subtotal, digits,
                f"El apunte de {line.name} debe valer lo mismo que su línea de factura")
        totals = move.tax_totals
        self.assertAlmostEqual(totals["total_amount_currency"], move.amount_total, digits,
                               "El widget debe coincidir con el asiento (moneda del documento)")
        self.assertAlmostEqual(totals["total_amount"], abs(move.amount_total_signed), 2,
                               "El widget debe coincidir con el asiento (VEF)")
        payment_term = move.line_ids.filtered(lambda l: l.display_type == "payment_term")
        self.assertAlmostEqual(totals["total_amount_foreign_currency"], sum(payment_term.mapped("foreign_debit")), 2,
                               "El alterno del widget debe coincidir con el de los apuntes")
        self.assertAlmostEqual(sum(move.line_ids.mapped("debit")), sum(move.line_ids.mapped("credit")), 2)
        self.assertAlmostEqual(sum(move.line_ids.mapped("foreign_debit")), sum(move.line_ids.mapped("foreign_credit")), 2)
        if expected_total is not None:
            self.assertAlmostEqual(move.amount_total, expected_total, digits,
                                   "Con IVA incluido el total debe ser lo digitado")

    def test_usd_included_with_exempt(self):
        lines = [(24.42, 4), (20.00, 2), (9.06, 4), (27.29, 2)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.usd, method, lines, ["exe", "incl", "incl", "incl"])
            self._assert_consistent(move, expected_total=228.50)
            self.assertAlmostEqual(abs(move.amount_total_signed), 9140.00, 2)

    def test_vef_included_with_exempt(self):
        lines = [(976.80, 4), (800.00, 2), (362.40, 4), (1091.60, 2)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.vef, method, lines, ["exe", "incl", "incl", "incl"])
            self._assert_consistent(move, expected_total=9140.00)

    def test_eur_included_with_exempt(self):
        lines = [(24.42, 4), (20.00, 2), (9.06, 4), (27.29, 2)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.eur, method, lines, ["exe", "incl", "incl", "incl"])
            self._assert_consistent(move, expected_total=228.50)

    def test_usd_mixed_included_excluded_exempt(self):
        lines = [(4.08, 1), (2.96, 2), (11.40, 1), (20.50, 3)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.usd, method, lines, ["incl", "excl", "incl", "exe"])
            self._assert_consistent(move)

    def test_usd_included_without_exempt_unchanged(self):
        lines = [(29.55, 1), (10.24, 2), (3.64, 4), (5.00, 1)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.usd, method, lines, ["incl", "incl", "incl", "incl"])
            self._assert_consistent(move, expected_total=69.59)

    def test_usd_included_with_price_included_exempt_tax(self):
        """Exento de 0 % marcado como incluido en el precio (no debe dividir entre cero)."""
        lines = [(24.42, 4), (20.00, 2), (9.06, 4), (27.29, 2)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.usd, method, lines, ["exei", "incl", "incl", "incl"])
            self._assert_consistent(move, expected_total=228.50)

    def test_tax_is_computed_on_company_currency_amounts(self):
        """El IVA incluido sale de los saldos en la moneda de la compañía (VEF):
        cada línea se pasa primero a VEF y el impuesto es la diferencia entre el
        total y la base de cada línea, también en VEF. Los apuntes cuadran en VEF
        y en alterno (ver `_assert_consistent`)."""
        company_currency = self.company.currency_id
        lines = [(24.42, 4), (20.00, 2), (9.06, 4), (27.29, 2)]
        move = self._invoice(self.usd, "round_globally", lines, ["exe", "incl", "incl", "incl"])
        rate = move.invoice_currency_rate
        expected_tax = 0.0
        for line in move.invoice_line_ids:
            raw_included = line.price_unit * line.quantity
            raw_base = raw_included
            if line.tax_ids == self.taxes["incl"]:
                raw_base = raw_included / 1.16
                expected_tax += company_currency.round(raw_included / rate) - company_currency.round(raw_base / rate)
            self.assertAlmostEqual(
                -line.balance, company_currency.round(raw_base / rate), 2,
                f"El saldo VEF de {line.name} debe salir de su importe convertido a VEF")
        tax_line = move.line_ids.filtered(lambda l: l.display_type == "tax")
        self.assertAlmostEqual(tax_line.credit, expected_tax, 2, "El IVA en VEF debe calcularse sobre bases VEF")
        self._assert_consistent(move, expected_total=228.50)

    def test_chained_subtotals_still_match_the_move(self):
        """Un grupo con `preceding_subtotal` genera un segundo subtotal en el
        widget (parte del total del anterior): debe seguir cuadrando con el
        asiento. La localización permite un solo impuesto por línea."""
        lines = [(24.42, 4), (20.00, 2), (9.06, 4), (27.29, 2)]
        for method in ("round_globally", "round_per_line"):
            move = self._invoice(self.usd, method, lines, ["exe", "incl", "incl", "extra"])
            self.assertGreater(len(move.tax_totals["subtotals"]), 1)
            self._assert_consistent(move, check_lines=False)

    def _group(self, move, name):
        groups = [g for st in move.tax_totals["subtotals"] for g in st["tax_groups"] if g["group_name"] == name]
        self.assertEqual(len(groups), 1, f"El widget debe traer el grupo {name}")
        return groups[0]

    def test_rounding_cent_stays_in_its_tax_group(self):
        """Con Global, la diferencia de redondeo cae en el grupo de impuesto al que
        pertenece y no en la línea de mayor base de toda la factura (una línea
        exenta). Caso reportado: precios de 4 decimales, tres líneas con IVA y una
        exenta con la mayor base. La base siempre es VEF: se comprueba también el
        monto en bolívares de cada grupo en `tax_totals`."""
        rate = 879.1225
        set_rate(self.env, self.usd, self.today, self.company, rate)
        set_rate(self.env, self.eur, self.today, self.company, rate)
        cc = self.company.currency_id
        for currency, factor in ((self.usd, 1.0), (self.eur, 1.0), (self.vef, rate)):
            iva_price, exempt_price = round(135.5130 * factor, 4), round(81.2835 * factor, 4)
            lines = [(iva_price, 1)] * 3 + [(exempt_price, 3)]
            move = self._invoice(currency, "round_globally", lines, ["excl", "excl", "excl", "exe"])
            with self.subTest(currency=currency.name):
                iva_lines = move.invoice_line_ids[:3]
                exempt_line = move.invoice_line_ids[3]
                exempt_expected = currency.round(exempt_price * 3)
                iva_expected = currency.round(iva_price * 3)
                # La línea exenta conserva su propia base (sin el centavo del grupo IVA).
                self.assertAlmostEqual(-exempt_line.amount_currency, exempt_expected, 2)
                self.assertAlmostEqual(-sum(iva_lines.mapped("amount_currency")), iva_expected, 2)
                # Los grupos del widget (documento y VEF) salen de sus propias líneas.
                exempt_group, iva_group = self._group(move, "Exento"), self._group(move, "IVA")
                self.assertAlmostEqual(exempt_group["base_amount_currency"], exempt_expected, 2)
                self.assertAlmostEqual(iva_group["base_amount_currency"], iva_expected, 2)
                self.assertAlmostEqual(exempt_group["base_amount"], -exempt_line.balance, 2)
                self.assertAlmostEqual(iva_group["base_amount"], -sum(iva_lines.mapped("balance")), 2)
                self.assertAlmostEqual(
                    -exempt_line.balance, cc.round(exempt_expected * (1.0 if currency == self.vef else rate)), 2,
                    "El saldo en VEF del exento no debe llevar el centavo del grupo IVA")
                self._assert_consistent(move, check_lines=False)

    def test_exempt_group_with_two_lines_keeps_its_own_cent(self):
        """Un grupo con varias líneas conserva su propia diferencia de redondeo: dos
        exentas de 10,006 suman 20,01 (no 20,02 línea por línea) aunque haya IVA incluido."""
        lines = [(10.006, 1), (10.006, 1), (30.00, 1), (20.00, 1)]
        move = self._invoice(self.usd, "round_globally", lines, ["exe", "exe", "incl", "incl"])
        exempt_lines = move.invoice_line_ids[:2]
        self.assertAlmostEqual(-sum(exempt_lines.mapped("amount_currency")), 20.01, 2)
        self.assertAlmostEqual(self._group(move, "Exento")["base_amount_currency"], 20.01, 2)
        self._assert_consistent(move, check_lines=False)

    def test_per_line_widget_matches_move_with_price_included_taxes(self):
        """Por línea con IVA incluido y precios de 4 decimales: la base del widget sale de
        las líneas reales (antes quedaba 0,01 por encima del asiento: 738,56 contra 738,55)."""
        lines = [(73.0150, 2), (60.2099, 1), (88.2215, 1), (111.0216, 4)]
        move = self._invoice(self.usd, "round_per_line", lines, ["incl", "exe", "incl", "incl"])
        self._assert_consistent(move, check_lines=False)
