import csv
import io
import json
import zipfile

from odoo.tests import HttpCase, TransactionCase, tagged

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


@tagged("post_install", "-at_install", "l10n_ve_sale_price_list")
class TestPricelistExportControllerHttp(HttpCase):
    """End-to-end checks of the actual /product/export/pricelist/ route -
    the unit-level tests above exercise _generate_rows in isolation, but
    never the route itself nor _generate_csv/_generate_xlsx, which only
    make sense wired to a real HTTP request (headers, content-type,
    request.env)."""

    def setUp(self):
        super().setUp()
        admin = self.env.ref("base.user_admin")
        admin.group_ids = [
            (4, self.env.ref("l10n_ve_sale_price_list.group_pricelist_report_multi").id)
        ]
        self.product = self.env["product.template"].create({
            "name": "HTTP Export Product",
            "type": "consu",
            "list_price": 42.0,
        })
        self.pricelist = self.env["product.pricelist"].create({"name": "HTTP Export Pricelist"})

    def _export(self, export_format):
        self.authenticate("admin", "admin")
        report_data = json.dumps({
            "pricelist_ids": [self.pricelist.id],
            "active_model": "product.template",
            "active_ids": [self.product.id],
        })
        return self.url_open(
            "/product/export/pricelist/",
            data={"report_data": report_data, "export_format": export_format},
        )

    def test_export_csv_route_returns_expected_rows(self):
        response = self._export("csv")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "text/csv")
        self.assertIn("Pricelist.csv", response.headers.get("Content-Disposition"))

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ["Product", "UOM", self.pricelist.display_name])
        self.assertEqual(rows[1][0], self.product.name)

    def test_export_xlsx_route_returns_legend_and_rows(self):
        response = self._export("xlsx")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Content-Type"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("Pricelist.xlsx", response.headers.get("Content-Disposition"))

        with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
            shared_strings = workbook.read("xl/sharedStrings.xml").decode()
        self.assertIn("Price list report", shared_strings)
        self.assertIn(self.env.company.display_name, shared_strings)
        self.assertIn(self.product.name, shared_strings)
