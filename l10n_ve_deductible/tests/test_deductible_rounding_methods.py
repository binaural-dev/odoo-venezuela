import random

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .common import ensure_ve_base


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleParityWithNativeDiscounts(TransactionCase):
    """Exactly the same figures as the native % discount (percentage mode)
    and as `discount_fixed` (amount mode), for both rounding methods and bills
    in VEF or USD. Rates: latest stored (2026-09-29/28), 1 USD = 857.88/857.00."""

    RATES = (0.00116565386887513, 0.001166853246500782)
    METHODS = ("round_per_line", "round_globally")
    FIXED_SCENARIOS = [
        [(123.4567, 1)],
        [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)],
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.company.write(
            {"use_deductible": True, "discount_type": "percent"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Paridad"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex Par", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Prod Par", "supplier_taxes_id": [Command.set(cls.exempt.ids)]}
        )

    def _set_rate(self, rate):
        Rate = self.env["res.currency.rate"]
        Rate.search([("name", "=", fields.Date.today()), ("company_id", "=", self.company.id)]).unlink()
        Rate.create({"name": fields.Date.today(), "currency_id": self.vef.id,
                     "rate": 1.0, "company_id": self.company.id})
        Rate.create({"name": fields.Date.today(), "currency_id": self.usd.id,
                     "rate": rate, "company_id": self.company.id})

    def _bill(self, currency, lines, line_extra=None, **vals):
        line_extra = line_extra or (lambda i: {})
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "currency_id": currency.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({"product_id": self.product.id, "name": f"L{i}",
                                    "quantity": q, "price_unit": p,
                                    "tax_ids": [Command.set(self.exempt.ids)],
                                    **line_extra(i)})
                    for i, (p, q) in enumerate(lines)
                ],
                **vals,
            }
        )

    @staticmethod
    def _snapshot(bill):
        lines = bill.invoice_line_ids.sorted("id")
        totals = bill.tax_totals
        cc = bill.company_currency_line_totals or {}
        cc_lines = [cc.get(str(l.id), {}) for l in lines]
        return {
            "amount_untaxed": bill.amount_untaxed,
            "amount_total": bill.amount_total,
            "amount_total_signed": bill.amount_total_signed,
            "amount_residual": bill.amount_residual,
            "price_subtotal": [l.price_subtotal for l in lines],
            "price_total": [l.price_total for l in lines],
            "balance": [l.balance for l in lines],
            "amount_currency": [l.amount_currency for l in lines],
            "foreign_subtotal": [l.foreign_subtotal for l in lines],
            "foreign_price_total": [l.foreign_price_total for l in lines],
            "cc_subtotal": [e.get("subtotal") for e in cc_lines],
            "cc_price_unit": [e.get("price_unit") for e in cc_lines],
            "cc_discount_amount": [e.get("discount_amount") for e in cc_lines],
            "widget_base_ves": totals.get("base_amount"),
            "widget_base_currency": totals.get("base_amount_currency"),
            "widget_total_currency": totals.get("total_amount_currency"),
            "widget_total_foreign": totals.get("total_amount_foreign_currency"),
            "journal_balances": sorted(bill.line_ids.mapped("balance")),
            "journal_amount_currencies": sorted(bill.line_ids.mapped("amount_currency")),
        }

    def _assert_same(self, mine, reference):
        a, b = self._snapshot(mine), self._snapshot(reference)
        for key, value in a.items():
            self.assertEqual(value, b[key], key)

    def _combos(self):
        for method in self.METHODS:
            for currency in (self.usd, self.vef):
                for rate in self.RATES:
                    yield method, currency, rate

    def _check_percent(self, method, currency, rate, lines, pct):
        self.company.tax_calculation_rounding_method = method
        self._set_rate(rate)
        native = self._bill(currency, lines, lambda i: {"discount": pct})
        mine = self._bill(currency, lines, is_deductible=True,
                          global_deductible_type="percent", global_deductible_percent=pct)
        self._assert_same(mine, native)

    def test_percent_same_as_native_discount(self):
        for method, currency, rate in self._combos():
            for lines in self.FIXED_SCENARIOS:
                with self.subTest(method=method, currency=currency.name, rate=rate, lines=len(lines)):
                    self._check_percent(method, currency, rate, lines, 12.5)

    def _check_amount(self, method, currency, rate, lines, amount):
        self.company.tax_calculation_rounding_method = method
        self._set_rate(rate)
        self.company.discount_type = "percent"
        mine = self._bill(currency, lines, is_deductible=True,
                          global_deductible_type="amount", global_deductible_amount=amount)
        mine_values = self._snapshot(mine)
        amounts = mine.invoice_line_ids.sorted("id").mapped("global_deductible_line_amount")
        self.assertEqual(round(sum(amounts), 4), amount, "line amounts add up to the deductible")
        self.company.discount_type = "amount"
        try:
            fixed = self._bill(currency, lines, lambda i: {"discount_fixed": amounts[i]})
            fixed_values = self._snapshot(fixed)
        finally:
            self.company.discount_type = "percent"
        for key, value in mine_values.items():
            self.assertEqual(value, fixed_values[key], key)

    def test_amount_same_as_discount_fixed(self):
        for method, currency, rate in self._combos():
            for lines in self.FIXED_SCENARIOS:
                gross = sum(p * q for p, q in lines)
                with self.subTest(method=method, currency=currency.name, rate=rate, lines=len(lines)):
                    self._check_amount(method, currency, rate, lines, round(gross * 0.31, 2))

    def test_stress_random_bills(self):
        rnd = random.Random(20261016)
        for n in range(80):
            method = rnd.choice(self.METHODS)
            currency = rnd.choice((self.usd, self.vef))
            rate = rnd.choice(self.RATES)
            lines = [
                (round(rnd.uniform(0.01, 500), rnd.choice((2, 3, 4))), rnd.choice((1, 2, 3, 7, 13, 0.5, 2.25)))
                for _ in range(rnd.randint(1, 8))
            ]
            gross = sum(p * q for p, q in lines)
            if currency.round(gross) < 1.0:
                continue
            with self.subTest(n=n, method=method, currency=currency.name, rate=rate, lines=lines):
                if rnd.random() < 0.5:
                    self._check_percent(method, currency, rate, lines,
                                        round(rnd.uniform(0.5, 90), rnd.choice((0, 1, 2))))
                else:
                    self._check_amount(method, currency, rate, lines,
                                       round(rnd.uniform(0.01, 0.9) * gross, 2))

    @staticmethod
    def _ves(text):
        """Number inside a formatted monetary text ('$ 1,234.50', '9.00 Bs.F')."""
        import re
        return float(re.search(r"-?\d[\d,]*\.?\d*", text).group().replace(",", ""))

    def test_widget_rows_are_exact_and_add_up(self):
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self.company.tax_calculation_rounding_method = method
                self._set_rate(rate)
                lines = self.FIXED_SCENARIOS[1]
                bill = self._bill(currency, lines, is_deductible=True,
                                  global_deductible_type="amount", global_deductible_amount=77.77)
                totals = bill.tax_totals
                ves = self.vef
                first = bill.invoice_line_ids[0]
                self.assertEqual(
                    self._ves(totals["formatted_deductible_amount_ves"]),
                    ves.round(77.77 / first.currency_rate),
                )
                usd_rate = 1.0 if currency == self.usd else rate
                expected_usd = self.usd.round(
                    77.77 if currency == self.usd else 77.77 * rate
                )
                self.assertEqual(
                    self._ves(totals["formatted_deductible_amount_foreign"]),
                    expected_usd,
                )
                self.assertEqual(
                    round(self._ves(totals["formatted_deductible_original_ves"])
                          - self._ves(totals["formatted_deductible_amount_ves"]), 2),
                    round(totals["base_amount"], 2),
                )
