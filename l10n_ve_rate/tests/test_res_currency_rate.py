from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResCurrencyRateComputeRate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")

        cls.parent_company = cls.env["res.company"].create(
            {
                "name": "Matriz Test Rate",
            }
        )
        cls.child_company = cls.env["res.company"].create(
            {
                "name": "Sucursal Test Rate",
                "parent_id": cls.parent_company.id,
            }
        )

        cls.parent_rate = cls.env["res.currency.rate"].create(
            {
                "currency_id": cls.usd.id,
                "company_id": cls.parent_company.id,
                "name": "2024-01-01",
                "company_rate": 36.0,
            }
        )

    def test_child_without_own_rate_falls_back_to_parent(self):
        """A subsidiary without its own currency rate should use the rate
        configured on the closest parent company (matriz)."""
        result = (
            self.env["res.currency.rate"]
            .with_company(self.child_company)
            .compute_rate(self.usd.id, "2024-01-02")
        )
        self.assertTrue(result)
        self.assertEqual(result["foreign_rate"], self.parent_rate.inverse_company_rate)
        self.assertEqual(result["foreign_inverse_rate"], self.parent_rate.company_rate)

    def test_root_company_uses_own_rate_without_climbing(self):
        """A root company (no parent) with its own currency rate must use it
        directly, without needing to climb the hierarchy.

        Note: Odoo core (`res.currency.rate._check_company_id`) only allows
        currency rates to be created on main/root companies (branches without
        `parent_id` are the ones that can never have their own rate), so this
        case is exercised with the root `parent_company` itself instead of a
        subsidiary.
        """
        other_root_company = self.env["res.company"].create(
            {
                "name": "Otra Matriz Test Rate",
            }
        )
        other_rate = self.env["res.currency.rate"].create(
            {
                "currency_id": self.usd.id,
                "company_id": other_root_company.id,
                "name": "2024-01-01",
                "company_rate": 40.0,
            }
        )
        result = (
            self.env["res.currency.rate"]
            .with_company(other_root_company)
            .compute_rate(self.usd.id, "2024-01-02")
        )
        self.assertTrue(result)
        self.assertEqual(result["foreign_rate"], other_rate.inverse_company_rate)
        self.assertEqual(result["foreign_inverse_rate"], other_rate.company_rate)
        self.assertNotEqual(result["foreign_rate"], self.parent_rate.inverse_company_rate)
