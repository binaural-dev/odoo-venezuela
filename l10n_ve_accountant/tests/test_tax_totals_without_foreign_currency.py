import logging

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_no_foreign_currency")
class TestTaxTotalsWithoutForeignCurrency(TransactionCase):
    """
    Regression tests for a company WITHOUT `foreign_currency_id`.

    `res.company.foreign_currency_id` has no default and is not required, so on any
    freshly created database it is empty. In that state
    `account.tax._get_tax_totals_summary` used to hand an empty `res.currency()` to the
    core taxes helpers, which round against it and raise:

        ValueError: Expected singleton: res.currency()

    Because `sale.order.tax_totals` is a stored computed field, the ORM recomputes it
    while installing modules, so the crash aborted the installation of *any* module on
    a fresh database, not just a sale flow at runtime.
    """

    def setUp(self):
        super().setUp()

        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.company
        self.country_ve = self.env.ref("base.ve")

        self.company.write({
            "currency_id": self.currency_vef.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })
        # The condition under test: no foreign currency configured at all.
        self.company.foreign_currency_id = False

        self.partner = self.env["res.partner"].create({"name": "Cliente sin moneda extranjera"})
        self.tax = self._get_tax("sale")
        self.tax_purchase = self._get_tax("purchase")
        # `l10n_ve_accountant` enforces exactly one sales tax and one purchase tax per
        # product, so both have to be set explicitly instead of inheriting the company
        # defaults (which carry more than one).
        self.product = self.env["product.product"].create({
            "name": "Producto sin moneda extranjera",
            "type": "service",
            "list_price": 100.0,
            "taxes_id": [Command.set([self.tax.id])],
            "supplier_taxes_id": [Command.set([self.tax_purchase.id])],
        })

    def _get_tax(self, type_tax_use):
        """
        Reuse a tax already installed by the localisation. Creating one here is not
        practical: `account.tax` validates that its tax group shares the same
        `country_id`, so a hand-made tax/group pair has to reproduce the fiscal
        country wiring that the localisation data already sets up correctly.
        """
        tax = self.env["account.tax"].search([
            ("type_tax_use", "=", type_tax_use),
            ("company_id", "=", self.company.id),
            ("amount_type", "=", "percent"),
        ], limit=1)
        self.assertTrue(
            tax,
            f"No '{type_tax_use}' percent tax found for company {self.company.display_name}; "
            "the localisation data is expected to provide one.",
        )
        return tax

    def _create_sale_order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                Command.create({
                    "product_id": self.product.id,
                    "product_uom_qty": 2,
                    "price_unit": 100.0,
                    "tax_ids": [Command.set([self.tax.id])],
                })
            ],
        })

    def test_sale_order_tax_totals_does_not_raise(self):
        """The whole point of the fix: computing tax_totals must not raise."""
        self.assertFalse(
            self.company.foreign_currency_id,
            "The company must have no foreign currency for this test to be meaningful.",
        )
        order = self._create_sale_order()

        totals = order.tax_totals

        self.assertTrue(totals, "tax_totals must still be computed without a foreign currency.")
        self.assertAlmostEqual(totals["base_amount_currency"], 200.0, places=2)
        expected_tax = 200.0 * self.tax.amount / 100
        self.assertAlmostEqual(totals["tax_amount_currency"], expected_tax, places=2)

    def test_foreign_keys_are_neutral_not_missing(self):
        """
        Consumers (templates, reports, the website checkout) read these keys
        unconditionally, so they must exist with neutral values rather than be absent.
        """
        order = self._create_sale_order()

        totals = order.tax_totals

        self.assertFalse(totals["foreign_currency_id"])
        self.assertEqual(totals["ves_currency_id"], self.company.currency_id.id)
        self.assertEqual(totals["base_amount_foreign_currency"], 0.0)
        self.assertEqual(totals["tax_amount_foreign_currency"], 0.0)
        self.assertEqual(totals["total_amount_foreign_currency"], 0.0)

    def test_foreign_base_line_currency_is_never_empty(self):
        """
        `_prepare_foreign_base_line_for_taxes_computation` must never produce a base line
        whose `currency_id` is an empty recordset: the core helpers round against it.
        It must also honour the `currency_id` the caller passes in kwargs
        (sale.order.line does pass a safe one) before falling back to the company currency.
        """
        order = self._create_sale_order()
        line = order.order_line[0]

        base_line = line._prepare_foreign_base_line_for_taxes_computation()

        self.assertTrue(
            base_line["currency_id"],
            "The foreign base line must carry a non-empty currency.",
        )
        self.assertEqual(len(base_line["currency_id"]), 1, "Expected exactly one currency.")

    def test_stored_tax_totals_survive_a_recompute(self):
        """
        Mirrors what breaks during installation: forcing the ORM to recompute the stored
        computed fields must not raise.
        """
        order = self._create_sale_order()

        self.env.invalidate_all()
        self.env["sale.order"].browse(order.id).order_line.price_unit = 150.0
        self.env.flush_all()

        self.assertAlmostEqual(order.tax_totals["base_amount_currency"], 300.0, places=2)
