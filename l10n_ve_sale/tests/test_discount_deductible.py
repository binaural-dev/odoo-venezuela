from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_invoice.tools.discount import spread_amount

from .test_discount_schemes import TestDiscountSchemes

DEDUCTIBLE = {"is_deductible": True, "global_deductible_type": "percent", "global_deductible_percent": 5}


@tagged("post_install", "-at_install", "l10n_ve_sale_discount")
class TestDiscountDeductible(TestDiscountSchemes):
    """The global discount and the deductible exclude each other: the one in
    use blocks the other, whichever comes first."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_deductible = "is_deductible" in cls.env["account.move"]._fields
        if cls.has_deductible:
            cls.company.write(
                {
                    "use_deductible": True,
                    "deductible_scope": "both",
                    "global_discount_account_id": cls.global_account.id,
                }
            )

    def _invoice(self):
        order = self._order()
        order.action_confirm()
        return order._create_invoices()

    def test_global_discount_refused_on_deductible_invoice(self):
        if not self.has_deductible:
            self.skipTest("l10n_ve_deductible is not installed")
        invoice = self._invoice()
        invoice.write(DEDUCTIBLE)
        for scheme in ("global_subtotal", "global_total", "lines"):
            with self.subTest(scheme=scheme), self.assertRaisesRegex(UserError, "deductible"):
                invoice._apply_discount(scheme, "percent", 10)
        self.assertFalse(invoice.discount_mode)

    def test_deductible_refused_when_global_discount_in_use(self):
        if not self.has_deductible:
            self.skipTest("l10n_ve_deductible is not installed")
        for scheme in ("global_subtotal", "global_total"):
            with self.subTest(scheme=scheme):
                invoice = self._invoice()
                invoice._apply_discount(scheme, "percent", 10)
                with self.assertRaisesRegex(ValidationError, "global discount|previous discount"):
                    invoice.write(DEDUCTIBLE)

    def test_deductible_refused_when_line_discount_in_use(self):
        if not self.has_deductible:
            self.skipTest("l10n_ve_deductible is not installed")
        invoice = self._invoice()
        invoice.invoice_line_ids.write({"discount": 10.0})
        with self.assertRaises(ValidationError):
            invoice.write(DEDUCTIBLE)

    def test_deductible_alone_is_untouched(self):
        if not self.has_deductible:
            self.skipTest("l10n_ve_deductible is not installed")
        invoice = self._invoice()
        invoice.write(dict(DEDUCTIBLE, global_deductible_percent=10))
        self.assertTrue(invoice.is_deductible)
        self.assertFalse(invoice.discount_mode)

    def test_spread_amount_adds_up_and_respects_each_line(self):
        gross = {"a": 600.0, "b": 400.0, "c": 0.01}
        shares = spread_amount(100.0, gross, 0.01)
        self.assertAlmostEqual(sum(shares.values()), 100.0, 2)
        self.assertEqual(shares["c"], 0.0)
        self.assertTrue(all(shares[key] < gross[key] for key in gross))
        shares = spread_amount(100.0, {"a": 100.0, "b": 100.0, "c": 100.0}, 0.01)
        self.assertAlmostEqual(sum(shares.values()), 100.0, 2)
