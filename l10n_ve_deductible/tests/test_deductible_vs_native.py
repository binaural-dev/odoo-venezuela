from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .common import ensure_ve_base


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleVsNative(TransactionCase):
    """The deductible must behave like the native percentage discount and
    like l10n_ve_invoice's fixed-amount discount: same line subtotals,
    totals, journal items and company-currency totals."""

    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.company = cls.env.company
        cls.company.use_deductible = True
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Cmp"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex Cmp", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Prod Cmp", "supplier_taxes_id": [Command.set(cls.exempt.ids)]}
        )
        cls.gross = sum(p * q for p, q in cls.LINES)

    def _bill(self, line_extra=None, **vals):
        line_extra = line_extra or (lambda i, p, q: {})
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": f"L{i}",
                            "quantity": q,
                            "price_unit": p,
                            "tax_ids": [Command.set(self.exempt.ids)],
                            **line_extra(i, p, q),
                        }
                    )
                    for i, (p, q) in enumerate(self.LINES)
                ],
                **vals,
            }
        )

    def _snapshot(self, bill):
        lines = bill.invoice_line_ids.sorted("id")
        return {
            "subtotals": [l.price_subtotal for l in lines],
            "foreign_subtotals": [l.foreign_subtotal for l in lines],
            "untaxed": bill.amount_untaxed,
            "total": bill.amount_total,
            "residual": bill.amount_residual,
            "total_signed": abs(bill.amount_total_signed),
        }

    def _assert_same(self, a, b):
        """Exactly the same totals and line subtotals."""
        for key in ("untaxed", "total", "residual", "total_signed"):
            self.assertEqual(a[key], b[key], key)
        self.assertEqual(a["subtotals"], b["subtotals"])
        self.assertEqual(a["foreign_subtotals"], b["foreign_subtotals"])

    def _assert_balanced(self, bill):
        self.assertEqual(
            round(sum(bill.line_ids.mapped("debit")), 2), round(sum(bill.line_ids.mapped("credit")), 2)
        )
        payable = bill.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable")
        self.assertEqual(round(abs(sum(payable.mapped("balance"))), 2), round(abs(bill.amount_total_signed), 2))

    def test_percent_same_as_native_percent(self):
        native = self._bill(lambda i, p, q: {"discount": 12.5})
        mine = self._bill(is_deductible=True, global_deductible_type="percent", global_deductible_percent=12.5)
        self._assert_same(self._snapshot(native), self._snapshot(mine))
        self._assert_balanced(mine)

    def test_post_and_balance(self):
        for kwargs in (
            {"global_deductible_type": "percent", "global_deductible_percent": 12.5},
            {"global_deductible_type": "amount", "global_deductible_amount": 77.77},
        ):
            bill = self._bill(is_deductible=True, **kwargs)
            bill.action_post()
            self.assertEqual(bill.state, "posted")
            self._assert_balanced(bill)
