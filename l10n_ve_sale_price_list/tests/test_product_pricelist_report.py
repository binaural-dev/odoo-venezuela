from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale_price_list")
class TestProductPricelistReport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.product = self.env["product.template"].create(
            {
                "name": "Test Product Pricelist Report",
                "type": "consu",
                "list_price": 100.0,
            }
        )
        self.pricelist_1 = self.env["product.pricelist"].create(
            {
                "name": "Pricelist 1",
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "compute_price": "percentage",
                            "percent_price": 10,
                            "applied_on": "3_global",
                        },
                    )
                ],
            }
        )
        self.pricelist_2 = self.env["product.pricelist"].create(
            {
                "name": "Pricelist 2",
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "compute_price": "percentage",
                            "percent_price": 20,
                            "applied_on": "3_global",
                        },
                    )
                ],
            }
        )

    def test_get_report_data_multiple_pricelists(self):
        report_model = self.env["report.product.report_pricelist"]
        result = report_model._get_report_data(
            {
                "pricelist_ids": [self.pricelist_1.id, self.pricelist_2.id],
                "active_model": "product.template",
                "active_ids": [self.product.id],
            }
        )

        pricelists = result["pricelists"]
        self.assertEqual(set(pricelists.ids), {self.pricelist_1.id, self.pricelist_2.id})

        products_data = result["products"]
        self.assertEqual(len(products_data), 1)
        product_data = products_data[0]

        expected_price_1 = self.pricelist_1._get_product_price(self.product, 1)
        expected_price_2 = self.pricelist_2._get_product_price(self.product, 1)

        self.assertAlmostEqual(product_data["prices"][self.pricelist_1.id], expected_price_1)
        self.assertAlmostEqual(product_data["prices"][self.pricelist_2.id], expected_price_2)

    def test_no_pricelists_selected_returns_empty_prices(self):
        report_model = self.env["report.product.report_pricelist"]
        result = report_model._get_report_data(
            {
                "pricelist_ids": [],
                "active_model": "product.template",
                "active_ids": [self.product.id],
            }
        )

        self.assertFalse(result["pricelists"])
        self.assertEqual(result["products"][0]["prices"], {})

    def test_pagination_restricts_active_ids(self):
        extra_products = self.env["product.template"].create(
            [{"name": f"Paginated Product {i}", "type": "consu"} for i in range(5)]
        )
        all_ids = [self.product.id] + extra_products.ids

        report_model = self.env["report.product.report_pricelist"]

        page_1 = report_model._get_report_data(
            {
                "pricelist_ids": [self.pricelist_1.id],
                "active_model": "product.template",
                "active_ids": all_ids,
                "page": 1,
                "page_size": 2,
            }
        )
        page_2 = report_model._get_report_data(
            {
                "pricelist_ids": [self.pricelist_1.id],
                "active_model": "product.template",
                "active_ids": all_ids,
                "page": 2,
                "page_size": 2,
            }
        )

        self.assertEqual([p["id"] for p in page_1["products"]], all_ids[:2])
        self.assertEqual([p["id"] for p in page_2["products"]], all_ids[2:4])

    def test_no_page_size_returns_all_products(self):
        extra_products = self.env["product.template"].create(
            [{"name": f"Full Export Product {i}", "type": "consu"} for i in range(5)]
        )
        all_ids = [self.product.id] + extra_products.ids

        report_model = self.env["report.product.report_pricelist"]
        result = report_model._get_report_data(
            {
                "pricelist_ids": [self.pricelist_1.id],
                "active_model": "product.template",
                "active_ids": all_ids,
            }
        )

        self.assertEqual({p["id"] for p in result["products"]}, set(all_ids))

    def test_report_data_includes_printing_company_and_issue_date(self):
        report_model = self.env["report.product.report_pricelist"]
        result = report_model._get_report_data(
            {
                "pricelist_ids": [self.pricelist_1.id],
                "active_model": "product.template",
                "active_ids": [self.product.id],
            }
        )

        self.assertEqual(result["company"], self.env.company)
        self.assertEqual(result["issue_date"], fields.Date.context_today(report_model))

    def test_pdf_template_renders_with_company_and_date_header(self):
        report_model = self.env["report.product.report_pricelist"]
        render_values = report_model._get_report_data(
            {
                "pricelist_ids": [self.pricelist_1.id],
                "active_model": "product.template",
                "active_ids": [self.product.id],
            },
            report_type="pdf",
        )
        html = self.env["ir.qweb"]._render("product.report_pricelist_page", render_values)
        self.assertIn(self.product.name, html)
        self.assertIn(str(fields.Date.context_today(report_model)), html)
