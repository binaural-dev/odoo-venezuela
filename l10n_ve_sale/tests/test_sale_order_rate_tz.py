from datetime import date, datetime

from odoo.tests import TransactionCase, freeze_time, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderRateTz(TransactionCase):
    """
    date_order se guarda en UTC: una orden de las 9 pm en Venezuela (UTC-4) tiene
    date_order del día siguiente y debe tomar la tasa del día local.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.usd = cls.env.ref("base.USD")
        cls.company.currency_id = cls.env.ref("base.VEF")
        cls.company.foreign_currency_id = cls.usd
        cls.env.user.tz = "America/Caracas"
        cls.env = cls.env(context=dict(cls.env.context, tz="America/Caracas"))
        # Solo existe la tasa del día local (26); la del 27 aún no se ha cargado.
        cls.env["res.currency.rate"].create(
            {
                "name": date(2026, 10, 26),
                "currency_id": cls.usd.id,
                "company_id": cls.company.id,
                "company_rate": 1.0 / 40.0,
                "inverse_company_rate": 40.0,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Partner TZ"})

    # 2026-10-27 01:00 UTC = 2026-10-26 21:00 en Caracas
    @freeze_time("2026-10-27 01:00:00")
    def test_order_after_8pm_uses_local_day_rate(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "date_order": datetime(2026, 10, 27, 1, 0, 0),
            }
        )
        self.assertEqual(order._l10n_ve_rate_date(), date(2026, 10, 26))
        self.assertAlmostEqual(order.foreign_rate, 40.0)

    @freeze_time("2026-10-27 01:00:00")
    def test_order_confirmation_after_8pm(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "date_order": datetime(2026, 10, 27, 1, 0, 0),
                "order_line": [
                    (0, 0, {"product_id": self.env["product.product"].create(
                        {"name": "Service TZ", "type": "service", "list_price": 10.0}
                    ).id})
                ],
            }
        )
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertAlmostEqual(order.foreign_rate, 40.0)
