from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged

from .common import AssertMixin, ensure_ve_base, set_usd_rate


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleLiveForm(AssertMixin, TransactionCase):
    """After EVERY form step (value, price, quantity, new or removed product)
    the form shows exactly what a bill created directly with the same lines
    and deductible gives. Odoo re-prices a vendor line when its quantity
    changes, so the price is set again afterwards."""

    RATE = 0.00116565386887513
    METHODS = ("round_per_line", "round_globally")
    START = [(10.3333, 3), (7.1249, 7), (0.9999, 13)]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef, cls.usd = cls.env.ref("base.VEF"), cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.company.write({"use_deductible": True, "discount_type": "percent"})
        set_usd_rate(cls.env, cls.RATE)
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Live"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex Live", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Prod Live", "supplier_taxes_id": [Command.set(cls.exempt.ids)]}
        )

    def _form(self, currency):
        form = Form(self.env["account.move"].with_context(default_move_type="in_invoice"))
        form.partner_id = self.partner
        form.invoice_date = fields.Date.today()
        form.currency_id = currency
        return form

    def _add_line(self, form, price, qty):
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product
            line.quantity = qty
            line.price_unit = price

    def _lines_of(self, form, with_amount):
        """[(price, qty, price_subtotal, deductible amount | None)] as shown."""
        out = []
        for index in range(len(form.invoice_line_ids)):
            with form.invoice_line_ids.edit(index) as line:
                out.append(
                    (
                        line.price_unit,
                        line.quantity,
                        line.price_subtotal,
                        line.global_deductible_line_amount if with_amount else None,
                    )
                )
        return out

    def _direct(self, currency, lines, **deductible):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "currency_id": currency.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({"product_id": self.product.id, "name": "L",
                                    "quantity": q, "price_unit": p,
                                    "tax_ids": [Command.set(self.exempt.ids)]})
                    for p, q, *_ in lines
                ],
                **deductible,
            }
        )

    def _check(self, form, currency, mode, value, step):
        """The form shows exactly what a bill created directly would have."""
        with_amount = mode == "amount"
        shown = self._lines_of(form, with_amount)
        deductible = {"is_deductible": True, "global_deductible_type": mode}
        deductible["global_deductible_amount" if with_amount else "global_deductible_percent"] = value
        direct = self._direct(currency, shown, **deductible)
        dlines = direct.invoice_line_ids.sorted("id")
        totals = form.tax_totals
        msg = f"after: {step}"
        self.assertEqual(round(totals["base_amount_currency"], 2), direct.amount_untaxed, f"untaxed {msg}")
        self.assertEqual(round(totals["total_amount_currency"], 2), direct.amount_total, f"total {msg}")
        self.assertEqual([s[2] for s in shown], dlines.mapped("price_subtotal"), f"line subtotals {msg}")
        if with_amount:
            amounts = [s[3] for s in shown]
            self.assertEqual(amounts, dlines.mapped("global_deductible_line_amount"), f"line amounts {msg}")
            self.assertEqual(round(sum(amounts), 2), value, f"line amounts add up to the amount {msg}")
        return direct

    def _scenario(self, currency, mode, value, new_value):
        form = self._form(currency)
        for price, qty in self.START:
            self._add_line(form, price, qty)
        form.is_deductible = True
        form.global_deductible_type = mode
        if mode == "amount":
            form.global_deductible_amount = value
        else:
            form.global_deductible_percent = value
        self._check(form, currency, mode, value, "value entered")
        with form.invoice_line_ids.edit(0) as line:
            line.price_unit = 50.1234
        self._check(form, currency, mode, value, "price edited")
        with form.invoice_line_ids.edit(1) as line:
            price = line.price_unit
            line.quantity = 4
            line.price_unit = price
        self._check(form, currency, mode, value, "quantity edited")
        self._add_line(form, 8.7654, 2)
        self._check(form, currency, mode, value, "product added")
        self._add_line(form, 19.9876, 5)
        with form.invoice_line_ids.edit(4) as line:
            line.quantity = 3
            line.price_unit = 21.5
        self._check(form, currency, mode, value, "product added and edited")
        form.invoice_line_ids.remove(index=1)
        self._check(form, currency, mode, value, "product removed")
        if mode == "amount":
            form.global_deductible_amount = new_value
        else:
            form.global_deductible_percent = new_value
        self._check(form, currency, mode, new_value, "value changed")
        bill = form.save()
        direct = self._direct(
            currency,
            [(l.price_unit, l.quantity) for l in bill.invoice_line_ids],
            is_deductible=True, global_deductible_type=mode,
            **{"global_deductible_amount" if mode == "amount" else "global_deductible_percent": new_value},
        )
        self.assertEqual(bill.amount_untaxed, direct.amount_untaxed)
        self.assertEqual(bill.amount_total_signed, direct.amount_total_signed)
        self.assertEqual(bill.invoice_line_ids.mapped("balance"), direct.invoice_line_ids.mapped("balance"))
        if mode == "amount":
            self.assertEqual(round(sum(bill.invoice_line_ids.mapped("global_deductible_line_amount")), 2), new_value)
        return bill

    def test_fixed_amount_every_step(self):
        for method in self.METHODS:
            for currency in (self.usd, self.vef):
                with self.subTest(method=method, currency=currency.name):
                    self.company.tax_calculation_rounding_method = method
                    self._scenario(currency, "amount", 20.0, 33.33)

    def test_percentage_every_step(self):
        for method in self.METHODS:
            for currency in (self.usd, self.vef):
                with self.subTest(method=method, currency=currency.name):
                    self.company.tax_calculation_rounding_method = method
                    self._scenario(currency, "percent", 12.5, 33.0)

    def test_saved_bill_edited_in_the_form(self):
        """Open a saved deductible bill, edit prices/quantities/lines and the
        amount, save: the amounts per line keep adding up to the amount."""
        for method in self.METHODS:
            with self.subTest(method=method):
                self.company.tax_calculation_rounding_method = method
                bill = self._direct(self.usd, self.START, is_deductible=True,
                                    global_deductible_type="amount",
                                    global_deductible_amount=20.0)
                with Form(bill) as form:
                    with form.invoice_line_ids.edit(0) as line:
                        line.price_unit = 77.7777
                    with form.invoice_line_ids.edit(2) as line:
                        line.quantity = 20
                        line.price_unit = 0.9999
                    self._add_line(form, 13.1313, 6)
                    form.global_deductible_amount = 41.41
                self.assertEqual(round(sum(bill.invoice_line_ids.mapped("global_deductible_line_amount")), 2), 41.41)
                direct = self._direct(
                    self.usd, [(l.price_unit, l.quantity) for l in bill.invoice_line_ids],
                    is_deductible=True, global_deductible_type="amount",
                    global_deductible_amount=41.41,
                )
                self.assertEqual(bill.amount_untaxed, direct.amount_untaxed)
                self.assertEqual(bill.invoice_line_ids.mapped("balance"),
                                 direct.invoice_line_ids.mapped("balance"))
