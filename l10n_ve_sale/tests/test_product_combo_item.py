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
