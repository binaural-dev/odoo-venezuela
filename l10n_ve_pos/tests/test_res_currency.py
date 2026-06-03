from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "res_currency")
class ResCurrencyTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_vef = cls.env["res.currency"].search([("name", "=", "VEF")], limit=1)
        if cls.currency_vef:
            cls.company.currency_id = cls.currency_vef
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_eur = cls.env.ref("base.EUR")
        cls.company.foreign_currency_id = cls.currency_usd

    def test_01_load_pos_data_domain_with_foreign_currency(self):
        data = {
            "company_id": str(self.company.id),
            "currency_id": str(self.company.currency_id.id),
        }
        domain = self.env["res.currency"]._load_pos_data_domain(data, data)
        self.assertIsInstance(domain, list)
        self.assertEqual(domain[0][0], "id")
        self.assertEqual(domain[0][1], "in")
        self.assertIn(self.company.currency_id.id, domain[0][2])
        self.assertIn(self.currency_usd.id, domain[0][2])

    def test_02_load_pos_data_domain_without_foreign_currency(self):
        self.company.foreign_currency_id = False
        data = {
            "company_id": str(self.company.id),
            "currency_id": str(self.company.currency_id.id),
        }
        domain = self.env["res.currency"]._load_pos_data_domain(data, data)
        self.assertIsInstance(domain, list)
