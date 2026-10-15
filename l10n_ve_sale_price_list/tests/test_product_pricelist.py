from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale_price_list")
class TestProductPricelistDisplayName(TransactionCase):
    def test_display_name_includes_company_when_set(self):
        company = self.env["res.company"].create({"name": "Test Company Display Name"})
        pricelist = self.env["product.pricelist"].create(
            {"name": "Pricelist With Company", "company_id": company.id}
        )
        self.assertIn("(Test Company Display Name)", pricelist.display_name)
        self.assertTrue(pricelist.display_name.startswith("Pricelist With Company ("))

    def test_display_name_unchanged_without_company(self):
        pricelist = self.env["product.pricelist"].create(
            {"name": "Pricelist Without Company", "company_id": False}
        )
        self.assertNotIn("(Test Company", pricelist.display_name)
        currency_suffix = f"({pricelist.currency_id.name})"
        self.assertTrue(pricelist.display_name.endswith(currency_suffix))
