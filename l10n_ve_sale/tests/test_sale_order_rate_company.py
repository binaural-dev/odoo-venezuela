from datetime import date, datetime

from odoo.tests import TransactionCase, freeze_time, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderRateCompany(TransactionCase):
    """La tasa de la orden sale de la compañía de la orden, no de la compañía activa
    del selector: con A activa (sin tasa) una orden de B usa la tasa de B."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        companies = cls.env["res.company"]
        for name in ("Venta A sin tasa", "Venta B con tasa"):
            companies |= companies.create({
                "name": name,
                "currency_id": cls.vef.id,
                "foreign_currency_id": cls.usd.id,
            })
        cls.company_a, cls.company_b = companies
        # La fecha de la tasa sale de date_order (la de creación la pone la base, sin freeze_time).
        companies.update_sale_order_rate_using_date_order = True
        cls.env.user.company_ids |= companies
        cls.env.user.tz = "America/Caracas"
        # VEF = 1 también: hay localizaciones (turaser) que exigen la tasa del día de
        # la moneda de la compañía.
        for currency, rate in ((cls.usd, 1.0 / 40.0), (cls.vef, 1.0)):
            cls.env["res.currency.rate"].with_company(cls.company_b).create({
                "currency_id": currency.id,
                "company_id": cls.company_b.id,
                "name": date(2026, 10, 26),
                "rate": rate,
            })
        cls.partner = cls.env["res.partner"].create({"name": "Cliente multicompañía", "company_id": False})

    @freeze_time("2026-10-26 15:00:00")
    def test_order_of_other_company_uses_its_rate(self):
        env_b = self.env(context=dict(self.env.context, allowed_company_ids=[self.company_b.id]))
        order = env_b["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company_b.id,
            "date_order": datetime(2026, 10, 26, 15, 0),
        })
        self.assertAlmostEqual(order.foreign_rate, 40.0)

        # Con A activa y B también seleccionada (el selector de compañías del cliente).
        env_a = self.env(context=dict(
            self.env.context, allowed_company_ids=[self.company_a.id, self.company_b.id]
        ))
        order = order.with_env(env_a)
        order.foreign_rate = 0.0
        order._compute_rate()

        self.assertAlmostEqual(order.foreign_rate, 40.0)
