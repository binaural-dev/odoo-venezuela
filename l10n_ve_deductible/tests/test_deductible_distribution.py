from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged

from .common import AssertMixin, ensure_ve_base


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleDistribution(AssertMixin, TransactionCase):
    """Distribution of the deductible over lines with Product Price
    precision greater than 2 decimals."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.env.company.use_deductible = True
        cls.env.company.tax_calculation_rounding_method = "round_globally"
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Dist"})
        cls.product = cls.env["product.product"].create({"name": "Prod Dist"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex Dist", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.product.supplier_taxes_id = cls.exempt

    def _line(self, price, qty=1.0):
        return Command.create(
            {
                "product_id": self.product.id,
                "name": "L",
                "quantity": qty,
                "price_unit": price,
                "tax_ids": [Command.set(self.exempt.ids)],
            }
        )

    def _bill(self, lines, **vals):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": lines,
                **vals,
            }
        )

    def _gross(self, bill):
        return sum(l.price_unit * l.quantity for l in bill.invoice_line_ids)

    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]

    def _lines(self):
        return [self._line(p, q) for p, q in self.LINES]

    def _assert_total(self, bill, deducted):
        """The bill total is what a native fixed discount with the very same
        per-line amounts gives (see test_deductible_rounding_methods)."""
        amounts = bill._get_deductible_line_amounts()
        self.assertEqual(round(sum(amounts.values()), 4), round(deducted, 4))
        gross = self._gross(bill)
        self.assertEqual(
            bill.amount_untaxed, bill.currency_id.round(gross - sum(amounts.values()))
        )
        self.assertEqual(bill.amount_total, bill.amount_untaxed)

    def _assert_same_as_native_percent(self, bill, pct):
        """Same bill totals as the native percentage discount."""
        native = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {"product_id": self.product.id, "name": "N", "discount": pct,
                         "quantity": l.quantity, "price_unit": l.price_unit,
                         "tax_ids": [Command.set(self.exempt.ids)]}
                    )
                    for l in bill.invoice_line_ids
                ],
            }
        )
        self.assertEqual(bill.amount_untaxed, native.amount_untaxed)
        self.assertEqual(bill.amount_total, native.amount_total)
        self.assertEqual(
            bill.invoice_line_ids.mapped("price_subtotal"),
            native.invoice_line_ids.mapped("price_subtotal"),
        )

    def test_amount_distribution(self):
        bill = self._bill(
            self._lines(), is_deductible=True, global_deductible_type="amount", global_deductible_amount=77.77
        )
        self._assert_total(bill, 77.77)
        self.assertEqual(bill.global_deductible_reference_amount, 77.77)
        gross_total = self._gross(bill)
        amounts = bill._get_deductible_line_amounts()
        for line in bill.invoice_line_ids:
            gross = line.price_unit * line.quantity
            self.assertEqual(
                round(line.global_deductible_discount_percent * gross / 100.0, 3),
                round(amounts[line], 3),
            )
            self.assertLessEqual(abs(amounts[line] - 77.77 * gross / gross_total), 0.0101)

    def test_percent_distribution(self):
        bill = self._bill(
            self._lines(), is_deductible=True, global_deductible_type="percent", global_deductible_percent=12.5
        )
        self._assert_same_as_native_percent(bill, 12.5)

    def test_deactivate_reverts_everything(self):
        bill = self._bill(
            self._lines(), is_deductible=True, global_deductible_type="amount", global_deductible_amount=77.77
        )
        gross = self._gross(bill)
        bill.is_deductible = False
        self.assertFalse(any(bill.invoice_line_ids.mapped("global_deductible_discount_percent")))
        self.assertFalse(any(bill.invoice_line_ids.mapped("discount")))
        self.assertEqual(bill.amount_total, bill.currency_id.round(gross))
        self.assertFalse(bill.tax_totals.get("is_deductible"))
        self.assertEqual(bill.global_deductible_amount, 0.0)
        self.assertEqual(bill.global_deductible_percent, 0.0)

    def test_price_change_redistributes_amount(self):
        bill = self._bill(
            self._lines(), is_deductible=True, global_deductible_type="amount", global_deductible_amount=77.77
        )
        bill.invoice_line_ids[0].price_unit = 55.5555
        bill.invoice_line_ids[2].quantity = 40
        self._assert_total(bill, 77.77)

    def test_new_line_redistributes_amount(self):
        bill = self._bill(
            self._lines(), is_deductible=True, global_deductible_type="amount", global_deductible_amount=77.77
        )
        bill.write({"invoice_line_ids": [self._line(19.9876, 4)]})
        self.assertEqual(len(bill.invoice_line_ids), len(self.LINES) + 1)
        self._assert_total(bill, 77.77)

    def test_price_change_percent(self):
        bill = self._bill(
            self._lines(), is_deductible=True, global_deductible_type="percent", global_deductible_percent=12.5
        )
        bill.invoice_line_ids[1].price_unit = 99.9999
        self._assert_same_as_native_percent(bill, 12.5)

    def test_amount_invalid_after_price_decrease(self):
        """Lowering prices so the fixed amount reaches the gross is rejected."""
        bill = self._bill(
            [self._line(10.0, 1), self._line(10.0, 1)],
            is_deductible=True,
            global_deductible_type="amount",
            global_deductible_amount=15.0,
        )
        from odoo.exceptions import ValidationError

        with self.assertRaisesMsg(ValidationError, "less than the original bill total"):
            bill.invoice_line_ids.write({"price_unit": 5.0})

    def test_form_live_flow(self):
        """Same flow through the form (onchanges), as the user does it."""
        rnd = self.env.company.currency_id.round
        form = Form(self.env["account.move"].with_context(default_move_type="in_invoice"))
        form.partner_id = self.partner
        form.invoice_date = fields.Date.today()
        for price, qty in self.LINES[:3]:
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = qty
                line.price_unit = price
        form.is_deductible = True
        form.global_deductible_type = "amount"
        form.global_deductible_amount = 20.0
        gross = sum(p * q for p, q in self.LINES[:3])
        self.assertEqual(rnd(form.tax_totals['base_amount_currency']), rnd(gross - 20.0))
        with form.invoice_line_ids.edit(0) as line:
            line.price_unit = 50.1234
        gross = 50.1234 * self.LINES[0][1] + sum(p * q for p, q in self.LINES[1:3])
        self.assertEqual(rnd(form.tax_totals['base_amount_currency']), rnd(gross - 20.0))
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product
            line.quantity = 2
            line.price_unit = 8.7654
        gross += 8.7654 * 2
        self.assertEqual(rnd(form.tax_totals['base_amount_currency']), rnd(gross - 20.0))
        form.is_deductible = False
        self.assertEqual(rnd(form.tax_totals['base_amount_currency']), rnd(gross))
        bill = form.save()
        self.assertFalse(any(bill.invoice_line_ids.mapped("global_deductible_discount_percent")))
