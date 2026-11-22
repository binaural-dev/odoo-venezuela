from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSystrayRate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # La moneda de la compañía no se toca (no se puede si ya hay asientos):
        # se usa como foránea cualquier otra moneda.
        usd = cls.env.ref("base.USD")
        cls.usd = usd if cls.company.currency_id != usd else cls.env.ref("base.EUR")
        cls.usd.active = True
        cls.company.write({"rate_systray_currency_id": cls.usd.id, "show_rate_systray": True})
        cls.env["res.currency.rate"].search(
            [("currency_id", "=", cls.usd.id), ("company_id", "in", [cls.company.id, False])]
        ).unlink()
        cls.today = fields.Date.context_today(cls.env["res.currency.rate"])

    def _create_rate(self, date, bs_per_usd, company=None):
        return self.env["res.currency.rate"].create(
            {
                "currency_id": self.usd.id,
                "company_id": (company if company is not None else self.company).id,
                "name": date,
                "rate": 1 / bs_per_usd,
            }
        )

    def test_rate_of_today_is_flagged_today(self):
        self._create_rate(self.today - timedelta(days=1), 900.0)
        self._create_rate(self.today, 950.0)

        data = self.env["res.currency.rate"].get_systray_rate()

        self.assertTrue(data["is_today"])
        self.assertAlmostEqual(data["rate"], 950.0, places=4)
        self.assertEqual(data["date"], fields.Date.to_string(self.today))

    def test_old_rate_is_not_today(self):
        old_date = self.today - timedelta(days=3)
        self._create_rate(old_date, 900.0)

        data = self.env["res.currency.rate"].get_systray_rate()

        self.assertFalse(data["is_today"])
        self.assertAlmostEqual(data["rate"], 900.0, places=4)
        self.assertEqual(data["date"], fields.Date.to_string(old_date))

    def test_future_rate_is_ignored(self):
        self._create_rate(self.today - timedelta(days=1), 900.0)
        self._create_rate(self.today + timedelta(days=1), 999.0)

        data = self.env["res.currency.rate"].get_systray_rate()

        self.assertFalse(data["is_today"])
        self.assertAlmostEqual(data["rate"], 900.0, places=4)

    def test_no_rate_is_reported_without_rate(self):
        data = self.env["res.currency.rate"].get_systray_rate()

        self.assertFalse(data["rate"])
        self.assertFalse(data["date"])
        self.assertFalse(data["is_today"])
        self.assertEqual(data["foreign_currency"], self.usd.name)

    def test_disabled_in_company_returns_empty(self):
        self._create_rate(self.today, 950.0)
        self.company.show_rate_systray = False

        self.assertEqual(self.env["res.currency.rate"].get_systray_rate(), {})

    def test_rate_without_company_is_used(self):
        self._create_rate(self.today, 950.0, company=self.env["res.company"])

        data = self.env["res.currency.rate"].get_systray_rate()

        self.assertTrue(data["is_today"])
        self.assertAlmostEqual(data["rate"], 950.0, places=4)

    def test_rate_is_shown_as_weak_currency_per_strong_one(self):
        """Si la moneda elegida es la débil (compañía en USD que muestra Bs), la
        tasa se expresa en esa moneda: Bs por USD, no USD por Bs."""
        self.env["res.currency.rate"].create(
            {
                "currency_id": self.usd.id,
                "company_id": self.company.id,
                "name": self.today,
                "rate": 950.0,  # 950 unidades de la moneda elegida por 1 de la compañía
            }
        )

        data = self.env["res.currency.rate"].get_systray_rate()

        self.assertAlmostEqual(data["rate"], 950.0, places=4)
        self.assertEqual(data["currency"], self.usd.name)
        self.assertEqual(data["foreign_currency"], self.company.currency_id.name)

    def test_default_currency_depends_on_company_currency(self):
        usd = self.env.ref("base.USD")
        vef = self.env.ref("base.VEF")
        vef.active = True
        company_usd = self.env["res.company"].create({"name": "Test USD", "currency_id": usd.id})
        company_vef = self.env["res.company"].create({"name": "Test VEF", "currency_id": vef.id})

        self.assertEqual(company_usd.rate_systray_currency_id, vef)
        self.assertEqual(company_vef.rate_systray_currency_id, usd)

    def test_chosen_currency_is_kept(self):
        eur = self.env.ref("base.EUR")
        self.company.rate_systray_currency_id = eur

        self.company._compute_rate_systray_currency_id()

        self.assertEqual(self.company.rate_systray_currency_id, eur)
