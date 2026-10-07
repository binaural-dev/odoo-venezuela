from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("l10n_ve_sale", "post_install", "-at_install")
class TestSaleOrderLineComboPricingIntegration(TransactionCase):
    """Integration tests using real Odoo records instead of mocks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.product_uom = cls.env.ref("uom.product_uom_unit")
        cls.pricelist = cls.env["product.pricelist"].create({
            "name": "Test Pricelist",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer",
            "company_type": "company",
        })

        # Create two regular products for combo items
        cls.service_product = cls.env["product.product"].create({
            "name": "Medical Service",
            "type": "service",
            "list_price": 100.0,
            "uom_id": cls.product_uom.id,
        })
        cls.material_product = cls.env["product.product"].create({
            "name": "Medical Supply",
            "type": "consu",
            "list_price": 30.0,
            "uom_id": cls.product_uom.id,
        })

        # Create a combo with its items inline (combo_id is required NOT NULL)
        # Note: in Odoo 19, lst_price on product.combo.item is a related field
        # (readonly from product_id.lst_price), so we set the product price directly.
        cls.combo = cls.env["product.combo"].create({
            "name": "Medical Combo",
            "price_distribution": "by_item_type",
            "combo_item_ids": [
                Command.create({
                    "product_id": cls.service_product.id,
                    "item_type": "principal",
                }),
                Command.create({
                    "product_id": cls.material_product.id,
                    "item_type": "fixed_price",
                }),
            ],
        })
        cls.combo_item_principal = cls.combo.combo_item_ids[0]
        cls.combo_item_fixed = cls.combo.combo_item_ids[1]

        # Create a product template with type 'combo' (requires at least 1 combo choice)
        cls.combo_template = cls.env["product.template"].create({
            "name": "Test Combo Product",
            "type": "combo",
            "list_price": 150.0,
            "uom_id": cls.product_uom.id,
            "combo_ids": [(4, cls.combo.id)],
        })
        cls.combo_product = cls.combo_template.product_variant_id

    def test_real_combo_price_distribution(self):
        """Verify price distribution with real combo items in a sale order."""
        if "sale" not in self.env.registry._init_modules:
            self.skipTest("sale module not installed")

        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pricelist.id,
        })

        # Create a combo line (the main combo product)
        combo_line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.combo_product.id,
            "product_uom_qty": 1.0,
            "price_unit": 150.0,
        })

        # Create combo item lines
        line_principal = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.service_product.id,
            "product_uom_qty": 1.0,
            "linked_line_id": combo_line.id,
            "combo_item_id": self.combo_item_principal.id,
        })
        line_fixed = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.material_product.id,
            "product_uom_qty": 1.0,
            "linked_line_id": combo_line.id,
            "combo_item_id": self.combo_item_fixed.id,
        })

        # Verify the combo price distribution
        price_principal = line_principal._get_combo_item_display_price()
        price_fixed = line_fixed._get_combo_item_display_price()

        # Fixed price item should get its lst_price
        self.assertEqual(price_fixed, 30.0)

        # Principal should absorb the remainder (150 - 30 = 120)
        self.assertEqual(price_principal, 120.0)

    def test_real_combo_multiple_principals(self):
        """Verify price distribution with multiple principal items."""
        if "sale" not in self.env.registry._init_modules:
            self.skipTest("sale module not installed")

        # Create an additional principal combo item
        extra_product = self.env["product.product"].create({
            "name": "Extra Service",
            "type": "service",
            "list_price": 80.0,
            "uom_id": self.product_uom.id,
        })
        combo_item_extra = self.env["product.combo.item"].create({
            "combo_id": self.combo.id,
            "product_id": extra_product.id,
            "item_type": "principal",
        })

        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pricelist.id,
        })

        combo_line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.combo_product.id,
            "product_uom_qty": 1.0,
            "price_unit": 150.0,
        })

        # Create combo item lines (2 principals + 1 fixed)
        line_principal_1 = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.service_product.id,
            "product_uom_qty": 1.0,
            "linked_line_id": combo_line.id,
            "combo_item_id": self.combo_item_principal.id,
        })
        line_principal_2 = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": extra_product.id,
            "product_uom_qty": 1.0,
            "linked_line_id": combo_line.id,
            "combo_item_id": combo_item_extra.id,
        })
        line_fixed = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.material_product.id,
            "product_uom_qty": 1.0,
            "linked_line_id": combo_line.id,
            "combo_item_id": self.combo_item_fixed.id,
        })

        price_principal_1 = line_principal_1._get_combo_item_display_price()
        price_principal_2 = line_principal_2._get_combo_item_display_price()
        price_fixed = line_fixed._get_combo_item_display_price()

        # Fixed price should still be 30
        self.assertEqual(price_fixed, 30.0)

        # Total combo price = 150, fixed = 30, remaining for 2 principals = 120
        # Each principal should get 60
        self.assertEqual(price_principal_1, 60.0)
        self.assertEqual(price_principal_2, 60.0)

        # Total distributed = 30 + 60 + 60 = 150
        self.assertEqual(price_fixed + price_principal_1 + price_principal_2, 150.0)

    def _make_order_with_combo(self, combo, list_price=150.0):
        template = self.env["product.template"].create({
            "name": "Combo %s" % combo.name,
            "type": "combo",
            "list_price": list_price,
            "uom_id": self.product_uom.id,
            "combo_ids": [(4, combo.id)],
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pricelist.id,
        })
        combo_line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": template.product_variant_id.id,
            "product_uom_qty": 1.0,
        })
        return order, combo_line

    def _make_item_line(self, order, combo_line, item):
        return self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": item.product_id.id,
            "product_uom_qty": 1.0,
            "linked_line_id": combo_line.id,
            "combo_item_id": item.id,
        })

    def test_price_proration_option_splits_its_share_between_chosen_items(self):
        combo = self.env["product.combo"].create({
            "name": "Proration Combo",
            "combo_item_ids": [
                Command.create({"product_id": self.service_product.id}),
                Command.create({"product_id": self.material_product.id}),
            ],
        })
        self.assertEqual(combo.price_distribution, "native")
        order, combo_line = self._make_order_with_combo(combo)
        lines = [self._make_item_line(order, combo_line, item) for item in combo.combo_item_ids]

        prices = [line._get_combo_item_display_price() for line in lines]

        self.assertEqual(prices, [75.0, 75.0])

    def test_price_proration_option_with_single_item_keeps_native_price(self):
        combo = self.env["product.combo"].create({
            "name": "Proration Single",
            "combo_item_ids": [Command.create({"product_id": self.service_product.id})],
        })
        order, combo_line = self._make_order_with_combo(combo)
        line = self._make_item_line(order, combo_line, combo.combo_item_ids)

        self.assertEqual(line._get_combo_item_display_price(), 150.0)


    def test_combo_product_rejects_prices_that_make_items_negative(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Combo inválido",
                "type": "combo",
                "list_price": 20.0,
                "uom_id": self.product_uom.id,
                "combo_ids": [(4, self.combo.id)],
            })

    def test_combo_product_accepts_prices_that_fit(self):
        self.env["product.template"].create({
            "name": "Combo válido",
            "type": "combo",
            "list_price": 150.0,
            "uom_id": self.product_uom.id,
            "combo_ids": [(4, self.combo.id)],
        })


@tagged("l10n_ve_sale", "post_install", "-at_install")
class TestDistributeComboPrice(TransactionCase):
    def _distribute(self, price, entries):
        from odoo.addons.l10n_ve_sale.models.product_combo_item import distribute_combo_price
        return distribute_combo_price(price, entries, lambda amount: round(amount, 2))

    def test_fixed_percentage_and_principal_add_up(self):
        prices = self._distribute(100.0, [
            ("fixed", "fixed_price", 0.0, 20.0),
            ("pct", "percentage", 25.0, 0.0),
            ("main", "principal", 0.0, 0.0),
        ])
        self.assertEqual(prices, {"fixed": 20.0, "pct": 20.0, "main": 60.0})

    def test_rounding_residue_goes_to_last_principal(self):
        prices = self._distribute(100.0, [
            ("a", "principal", 0.0, 0.0),
            ("b", "principal", 0.0, 0.0),
            ("c", "principal", 0.0, 0.0),
        ])
        self.assertAlmostEqual(sum(prices.values()), 100.0)
        self.assertEqual(prices["a"], prices["b"])

    def test_without_principal_residue_goes_to_last_entry(self):
        prices = self._distribute(100.0, [
            ("fixed", "fixed_price", 0.0, 30.0),
            ("pct", "percentage", 50.0, 0.0),
        ])
        self.assertAlmostEqual(sum(prices.values()), 100.0)
        self.assertEqual(prices["fixed"], 30.0)

    def test_prorate_by_base_price_and_even_when_zero(self):
        from odoo.addons.l10n_ve_sale.models.product_combo_item import prorate_combo_price
        rnd = lambda amount: round(amount, 2)
        shares = prorate_combo_price(100.0, [("a", 10.0), ("b", 30.0)], rnd)
        self.assertEqual(shares, {"a": 25.0, "b": 75.0})
        even = prorate_combo_price(100.0, [("a", 0.0), ("b", 0.0), ("c", 0.0)], rnd)
        self.assertAlmostEqual(sum(even.values()), 100.0)
