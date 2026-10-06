from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command
from odoo.addons.l10n_ve_sale.models.sale_order_line import SaleOrderLine
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class FakeRecordset(list):
    def filtered(self, predicate):
        return FakeRecordset([record for record in self if predicate(record)])


class FakeCurrency:
    def __init__(self, digits=2):
        self.digits = digits
        self.convert_calls = []

    def round(self, amount):
        return round(amount, self.digits)

    def _convert(self, from_amount, to_currency, company, date):
        self.convert_calls.append(
            {
                "to_currency": to_currency,
                "company": company,
                "date": date,
            }
        )
        return from_amount


class FakeComboItem:
    def __init__(self, item_type, percentage=0.0, lst_price=0.0, currency=None):
        self.item_type = item_type
        self.percentage = percentage
        self.lst_price = lst_price
        self.currency_id = currency or FakeCurrency()


class FakeLine:
    def __init__(self, order, currency, combo_item=None, linked_line=None, combo_price=0.0):
        self.order_id = order
        self.currency_id = currency
        self.company_id = SimpleNamespace(id=99)
        self.combo_item_id = combo_item
        self._linked_line = linked_line
        self._combo_price = combo_price

    def ensure_one(self):
        return True

    def _get_linked_line(self):
        return self._linked_line

    def _get_display_price_ignore_combo(self):
        return self._combo_price


@tagged("l10n_ve_sale", "post_install", "-at_install")
class TestSaleOrderLineComboPricing(TransactionCase):
    def _get_parent_with_method(self, model_name, method_name):
        model_cls = type(self.env[model_name])
        for klass in model_cls.__mro__[1:]:
            if method_name in klass.__dict__:
                return klass
        self.fail("No super class found for %s.%s" % (model_name, method_name))

    def test_get_combo_item_display_price_falls_back_to_super(self):
        model_cls = type(self.env["sale.order.line"])
        parent_class = self._get_parent_with_method(
            "sale.order.line", "_get_combo_item_display_price"
        )
        line = self.env["sale.order.line"].new({})

        with patch.object(model_cls, "_get_linked_line", return_value=False), patch.object(
            parent_class, "_get_combo_item_display_price", return_value=42.0
        ):
            self.assertEqual(line._get_combo_item_display_price(), 42.0)

    def test_get_combo_item_display_price_distributes_with_principal_delta(self):
        combo_token = object()
        currency = FakeCurrency(digits=2)
        order = SimpleNamespace(order_line=FakeRecordset(), date_order=False)

        combo_line = FakeLine(order=order, currency=currency, linked_line=None, combo_price=100.0)

        fixed_line = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("fixed_price", lst_price=20.0, currency=currency),
            linked_line=combo_token,
        )
        percentage_line = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("percentage", percentage=50.0, currency=currency),
            linked_line=combo_token,
        )
        principal_line_1 = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("principal", currency=currency),
            linked_line=combo_token,
        )
        principal_line_2 = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("principal", currency=currency),
            linked_line=combo_token,
        )
        principal_line_3 = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("principal", currency=currency),
            linked_line=combo_token,
        )

        order.order_line = FakeRecordset(
            [
                fixed_line,
                percentage_line,
                principal_line_1,
                principal_line_2,
                principal_line_3,
            ]
        )

        for current in [fixed_line, percentage_line, principal_line_1, principal_line_2, principal_line_3]:
            current._linked_line = combo_line

        value_first_principal = SaleOrderLine._get_combo_item_display_price(principal_line_1)
        value_last_principal = SaleOrderLine._get_combo_item_display_price(principal_line_3)

        self.assertAlmostEqual(value_first_principal, 13.33, places=2)
        self.assertAlmostEqual(value_last_principal, 13.34, places=2)
        self.assertEqual(currency.convert_calls[0]["company"].id, 99)

    def test_get_combo_item_display_price_without_principal_assigns_delta(self):
        combo_token = object()
        currency = FakeCurrency(digits=2)
        order = SimpleNamespace(order_line=FakeRecordset(), date_order=False)

        combo_line = FakeLine(order=order, currency=currency, linked_line=None, combo_price=99.99)

        fixed_line = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("fixed_price", lst_price=33.33, currency=currency),
            linked_line=combo_token,
        )
        percentage_line = FakeLine(
            order=order,
            currency=currency,
            combo_item=FakeComboItem("percentage", percentage=50.0, currency=currency),
            linked_line=combo_token,
        )

        order.order_line = FakeRecordset([fixed_line, percentage_line])

        fixed_line._linked_line = combo_line
        percentage_line._linked_line = combo_line

        value_fixed = SaleOrderLine._get_combo_item_display_price(fixed_line)
        value_percentage = SaleOrderLine._get_combo_item_display_price(percentage_line)

        self.assertEqual(value_fixed, 33.33)
        self.assertEqual(value_percentage, 66.66)


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
