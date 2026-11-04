import random

from odoo import Command

from .common import DeductibleCase, set_usd_rate


class TestDeductibleParity(DeductibleCase):
    """Exactly the same figures as the native % discount (percentage mode) and
    as `discount_fixed` (amount mode, with the amounts stored per line), for
    both rounding methods and documents in VEF or USD."""

    SCENARIOS = [[(123.4567, 1)], DeductibleCase.LINES]

    def _check_percent(self, currency, lines, percent):
        native = self._doc(lines, currency, line_extra={"discount": percent})
        mine = self._doc(lines, currency, **self.PERCENT | {"global_deductible_percent": percent})
        self._assert_same(mine, native)

    def _check_amount(self, currency, lines, amount):
        self.company.discount_type = "percent"
        mine = self._doc(lines, currency, **self.AMOUNT | {"global_deductible_amount": amount})
        amounts = mine.invoice_line_ids.sorted("id").mapped("global_deductible_line_amount")
        self.assertEqual(round(sum(amounts), 2), amount, "the lines add up to the amount entered")
        mine_figures = self._snapshot(mine)
        self.company.discount_type = "amount"
        try:
            fixed = self._doc(
                currency=currency,
                invoice_line_ids=[
                    Command.create(
                        {"product_id": self.product.id, "name": "F", "quantity": qty, "price_unit": price,
                         "discount_fixed": share, "tax_ids": [Command.set(self.tax().ids)]}
                    )
                    for (price, qty), share in zip(lines, amounts)
                ],
            )
            fixed_figures = self._snapshot(fixed)
        finally:
            self.company.discount_type = "percent"
        for key, value in mine_figures.items():
            self.assertEqual(value, fixed_figures[key], key)

    def test_percent_equals_native_discount(self):
        for method, currency in self._combos():
            for lines in self.SCENARIOS:
                with self.subTest(method=method, currency=currency.name, lines=len(lines)):
                    self._check_percent(currency, lines, 12.5)

    def test_percent_equals_native_discount_with_taxed_lines(self):
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                tax = self.tax("general")
                native = self._doc(self.LINES, currency, tax=tax, line_extra={"discount": 12.5})
                mine = self._doc(self.LINES, currency, tax=tax, **self.PERCENT)
                self._assert_same(mine, native)
                self.assertTrue(mine.amount_tax)

    def test_amount_equals_discount_fixed(self):
        for method, currency in self._combos():
            for lines in self.SCENARIOS:
                gross = sum(price * qty for price, qty in lines)
                with self.subTest(method=method, currency=currency.name, lines=len(lines)):
                    self._check_amount(currency, lines, round(gross * 0.31, 2))

    def test_random_documents(self):
        rnd = random.Random(20261016)
        for n in range(60):
            method, currency = rnd.choice(self.METHODS), rnd.choice((self.usd, self.vef))
            lines = [
                (round(rnd.uniform(0.01, 500), rnd.choice((2, 3, 4))), rnd.choice((1, 2, 3, 7, 13, 0.5, 2.25)))
                for _line in range(rnd.randint(1, 8))
            ]
            gross = sum(price * qty for price, qty in lines)
            if currency.round(gross) < 1.0:
                continue
            with self.subTest(n=n, method=method, currency=currency.name, lines=lines):
                self.company.tax_calculation_rounding_method = method
                set_usd_rate(self.env, rnd.choice(self.RATES))
                if rnd.random() < 0.5:
                    self._check_percent(currency, lines, round(rnd.uniform(0.5, 90), rnd.choice((0, 1, 2))))
                else:
                    self._check_amount(currency, lines, round(rnd.uniform(0.01, 0.9) * gross, 2))

    def test_line_amounts_stay_exact_when_prices_or_lines_change(self):
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                doc = self._doc(currency=currency, **self.AMOUNT)
                for line in doc.invoice_line_ids:
                    gross = line.price_unit * line.quantity
                    self.assertLess(line.global_deductible_line_amount, gross)
                    self.assertEqual(
                        line.global_deductible_discount_percent,
                        (line.global_deductible_line_amount / gross) * 100.0,
                    )
                doc.invoice_line_ids[0].price_unit = 55.5555
                doc.write({"invoice_line_ids": [Command.create(
                    {"product_id": self.product.id, "name": "N", "quantity": 4, "price_unit": 19.9876,
                     "tax_ids": [Command.set(self.tax().ids)]})]})
                self.assertEqual(round(sum(doc.invoice_line_ids.mapped("global_deductible_line_amount")), 2), 77.77)
                lines = [(line.price_unit, line.quantity) for line in doc.invoice_line_ids]
                self._assert_same(doc, self._doc(lines, currency, **self.AMOUNT))

    def test_widget_rows_are_the_exact_conversion_and_add_up(self):
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                doc = self._doc(currency=currency, **self.AMOUNT)
                totals, rate = doc.tax_totals, doc.invoice_line_ids[0].currency_rate
                deducted_ves = self._number(totals["formatted_deductible_amount_ves"])
                self.assertEqual(deducted_ves, self.vef.round(77.77 / rate))
                original_ves = self._number(totals["formatted_deductible_original_ves"])
                self.assertEqual(round(original_ves - deducted_ves, 2), round(totals["base_amount"], 2))
                expected_foreign = 77.77 if currency == self.usd else self.usd.round(77.77 * self.RATES[0])
                self.assertEqual(self._number(totals["formatted_deductible_amount_foreign"]), expected_foreign)

    def test_detailed_amounts_add_up(self):
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                for values in (self.PERCENT, self.AMOUNT):
                    doc = self._doc(currency=currency, **values)
                    details = doc.detailed_amounts
                    gross = sum(line.price_unit * line.quantity for line in doc.invoice_line_ids)
                    self.assertEqual(details["gross_amount"], gross)
                    self.assertEqual(
                        round(details["gross_amount"] - details["discount_amount"], 2),
                        round(sum(doc.invoice_line_ids.mapped("price_subtotal")), 2),
                    )


class TestDeductibleParityCustomer(TestDeductibleParity):
    MOVE_TYPE = "out_invoice"
