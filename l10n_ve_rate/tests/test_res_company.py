from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResCompanyEffectiveForeignCurrency(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        cls.vef = cls.env.ref("base.VEF")

        cls.parent_company = cls.env["res.company"].create(
            {
                "name": "Matriz Test",
                "currency_id": cls.vef.id,
                "foreign_currency_id": cls.usd.id,
            }
        )
        cls.child_company = cls.env["res.company"].create(
            {
                "name": "Sucursal Test",
                "parent_id": cls.parent_company.id,
            }
        )

    def test_child_falls_back_to_parent_currency(self):
        """A subsidiary without its own foreign currency should inherit the
        parent's (matriz) configured foreign currency."""
        self.assertEqual(
            self.child_company._get_effective_foreign_currency(),
            self.usd,
        )

    def test_child_own_currency_is_not_overridden(self):
        """A subsidiary that has its own foreign currency configured must
        keep it, regardless of the parent's configuration."""
        self.child_company.foreign_currency_id = self.eur.id
        self.assertEqual(
            self.child_company._get_effective_foreign_currency(),
            self.eur,
        )

    def test_parent_without_currency_returns_empty(self):
        """If no company in the hierarchy has a foreign currency configured,
        the fallback should resolve to an empty recordset."""
        self.parent_company.foreign_currency_id = False
        self.assertFalse(
            self.child_company._get_effective_foreign_currency()
        )
