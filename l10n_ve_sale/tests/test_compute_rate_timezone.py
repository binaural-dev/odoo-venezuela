from datetime import datetime

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestComputeRateTimezone(TransactionCase):
    """``sale.order._compute_rate()`` computed ``rate_date`` straight off
    ``date_order.date()`` (UTC), landing one calendar day ahead of
    Venezuela's actual day. ``binaural_mobile``'s ``/budget/order/create``
    controller sets ``date_order`` to the raw server clock and then calls
    ``sale._compute_rate()`` directly right after creating the order --
    exactly the method under test here.

    ``date_order`` below is 2026-10-28 02:00 UTC, which is still
    2026-10-27 22:00 in America/Caracas (UTC-4) -- the exact "UTC already
    tomorrow" window reported against production.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.ves = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company.currency_id = cls.ves
        cls.company.foreign_currency_id = cls.usd
        cls.partner = cls.env["res.partner"].create({"name": "TZ Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "TZ Product",
            "list_price": 100.0,
        })

    def _create_order_with_frozen_rate(self, date_order):
        """``manually_set_rate``/explicit ``foreign_rate`` sidestep
        ``default_rate``/``default_inverse_rate`` and the extra
        ``compute_rate`` lookup in ``create()`` (both always keyed off the
        real wall-clock date, a separate concern from the one under test
        here), isolating ``_compute_rate()`` itself -- the method
        ``binaural_mobile`` calls explicitly after creating the order.
        """
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "date_order": date_order,
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product.id,
            "product_uom_qty": 1,
            "price_unit": 100.0,
        })
        so.manually_set_rate = False
        return so

    def test_rate_date_uses_venezuela_day_not_utc_day(self):
        """A rate exists only for 2026-10-27 (Venezuela's actual day).
        ``_compute_rate()`` must find it instead of looking for 10-28."""
        self.env["res.currency.rate"].create({
            "currency_id": self.usd.id,
            "company_id": self.company.id,
            "name": "2026-10-27",
            "rate": 1.0 / 380.0,
        })

        so = self._create_order_with_frozen_rate(datetime(2026, 10, 28, 2, 0, 0))
        so._compute_rate()

        self.assertEqual(so.foreign_rate_date, fields.Date.from_string("2026-10-27"))
        self.assertNotEqual(so.foreign_rate, 0.0)
