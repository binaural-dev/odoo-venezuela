from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_sale_price_list.controllers.pricelist_export import (
    ProductPricelistExportController,
)


@tagged("post_install", "-at_install", "l10n_ve_sale_price_list")
class TestPricelistExportController(TransactionCase):
    """Unit-level checks on the row/header building logic the controller
    uses for both CSV and XLSX, without going through an actual HTTP
    request (the `_generate_rows` helper doesn't touch `request` at all).
    """

    def setUp(self):
        super().setUp()
        self.pricelist_1 = self.env["product.pricelist"].create({"name": "Export Pricelist 1"})
        self.pricelist_2 = self.env["product.pricelist"].create({"name": "Export Pricelist 2"})
        self.controller = ProductPricelistExportController()

    def test_generate_rows_uses_prices_dict_per_pricelist(self):
        products_data = [
            {
                "id": 1,
                "name": "Product A",
                "uom": "Units",
                "prices": {self.pricelist_1.id: 10.0, self.pricelist_2.id: 20.0},
            }
        ]

        rows = self.controller._generate_rows(products_data, self.pricelist_1 + self.pricelist_2)

        self.assertEqual(rows, [["Product A", "Units", 10.0, 20.0]])

    def test_generate_rows_flattens_variants(self):
        products_data = [
            {
                "id": 1,
                "name": "Template A",
                "uom": "Units",
                "prices": {},
                "variants": [
                    {
                        "id": 11,
                        "name": "Template A - Red",
                        "uom": "Units",
                        "prices": {self.pricelist_1.id: 5.0},
                    },
                    {
                        "id": 12,
                        "name": "Template A - Blue",
                        "uom": "Units",
                        "prices": {self.pricelist_1.id: 6.0},
                    },
                ],
            }
        ]

        rows = self.controller._generate_rows(products_data, self.pricelist_1)

        self.assertEqual(
            rows,
            [
                ["Template A - Red", "Units", 5.0],
                ["Template A - Blue", "Units", 6.0],
            ],
        )

    def test_generate_rows_missing_price_defaults_to_zero(self):
        products_data = [{"id": 1, "name": "Product A", "uom": "Units", "prices": {}}]

        rows = self.controller._generate_rows(products_data, self.pricelist_1)

        self.assertEqual(rows, [["Product A", "Units", 0.0]])
