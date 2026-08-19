from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductCompanyEditRestriction(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group = self.env.ref("l10n_ve_stock.group_edit_product_company")
        self.user = self.env["res.users"].create({
            "name": "Test User Company Edit",
            "login": "test_user_company_edit",
            "email": "test_user_company_edit@example.com",
        })
        self.template = self.env["product.template"].create({
            "name": "Product Company Edit Restriction",
            "type": "consu",
        })

    def test_can_edit_company_id_false_without_group(self):
        template = self.template.with_user(self.user)
        self.assertFalse(template.can_edit_company_id)

    def test_can_edit_company_id_true_with_group(self):
        self.user.group_ids = [(4, self.group.id)]
        template = self.template.with_user(self.user)
        self.assertTrue(template.can_edit_company_id)
