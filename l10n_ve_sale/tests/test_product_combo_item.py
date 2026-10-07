from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("l10n_ve_sale", "post_install", "-at_install")
class TestProductComboItem(TransactionCase):
    def test_percentage_item_rejects_out_of_range_values(self):
        item = self.env["product.combo.item"].new(
            {
                "item_type": "percentage",
                "percentage": 120.0,
            }
        )

        with self.assertRaises(ValidationError):
            item._check_percentage_value()

    def test_percentage_item_accepts_valid_bounds(self):
        low_item = self.env["product.combo.item"].new(
            {
                "item_type": "percentage",
                "percentage": 0.0,
            }
        )
        high_item = self.env["product.combo.item"].new(
            {
                "item_type": "percentage",
                "percentage": 100.0,
            }
        )

        low_item._check_percentage_value()
        high_item._check_percentage_value()

    def test_non_percentage_item_is_not_validated_by_range(self):
        item = self.env["product.combo.item"].new(
            {
                "item_type": "fixed_price",
                "percentage": 500.0,
            }
        )

        item._check_percentage_value()

    def _item(self, mode, item_type, list_price):
        combo = self.env["product.combo"].new({"name": "Opción", "price_distribution": mode})
        product = self.env["product.product"].create({"name": "Producto", "list_price": list_price})
        return self.env["product.combo.item"].new(
            {"combo_id": combo, "item_type": item_type, "product_id": product.id}
        )

    def test_fixed_price_item_rejects_zero_priced_product(self):
        item = self._item("by_item_type", "fixed_price", 0.0)

        with self.assertRaises(ValidationError):
            item._check_fixed_price_value()

    def test_fixed_price_item_accepts_priced_product(self):
        self._item("by_item_type", "fixed_price", 10.0)._check_fixed_price_value()

    def test_principal_item_allows_zero_priced_product(self):
        self._item("by_item_type", "principal", 0.0)._check_fixed_price_value()

    def test_fixed_price_not_validated_when_option_uses_native_proration(self):
        self._item("native", "fixed_price", 0.0)._check_fixed_price_value()

