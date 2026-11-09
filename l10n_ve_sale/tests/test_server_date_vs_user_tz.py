"""A las 8 pm de Caracas el servidor (UTC) ya esta en el dia siguiente.

`sale.order.date_order` es un Datetime en UTC y `_compute_rate` hace
`date_order.date()`: obtiene la fecha UTC (manana) en vez de la del usuario y
`compute_rate` lanza "no hay tasa asignada" aunque la tasa del dia del usuario
existe. Estas pruebas FALLAN mientras se use la fecha UTC.
"""

from odoo.addons.l10n_ve_accountant.tests.common_tz_boundary import (
    CARACAS_DAY,
    FROZEN_UTC_NOW,
    USD_PER_VEF_INVERSE,
    TzBoundaryMixin,
    freeze_time,
)
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale_tz_boundary")
class TestSaleOrderServerDateVsUserTz(TzBoundaryMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._setup_tz_boundary()
        self.partner = self.env["res.partner"].create({"name": "TZ Sale Partner"})

    def _assert_caracas_day_rate(self, order):
        self.assertAlmostEqual(
            order.foreign_rate,
            USD_PER_VEF_INVERSE,
            places=4,
            msg=(
                "A las 8 pm de Caracas la orden debe tomar la tasa del dia del "
                f"usuario ({CARACAS_DAY}), no la del dia UTC."
            ),
        )

    def test_order_created_at_8pm_uses_user_day_rate(self):
        """Sin date_order explicito: el default es Datetime.now() (00:30 UTC)."""
        with freeze_time(FROZEN_UTC_NOW):
            order = self.env["sale.order"].create({"partner_id": self.partner.id})
            self._assert_caracas_day_rate(order)
            self.assertEqual(order.foreign_rate_date, CARACAS_DAY)

    def test_order_with_explicit_date_order_at_8pm_uses_user_day_rate(self):
        """date_order llega como Datetime UTC igual que lo guarda el cliente web."""
        with freeze_time(FROZEN_UTC_NOW):
            order = self.env["sale.order"].create(
                {"partner_id": self.partner.id, "date_order": "2026-03-11 00:30:00"}
            )
            self._assert_caracas_day_rate(order)

    def test_confirm_order_at_8pm_does_not_require_next_day_rate(self):
        product = self.env["product.product"].create(
            {"name": "TZ Servicio", "type": "service", "list_price": 100.0}
        )
        with freeze_time(FROZEN_UTC_NOW):
            order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (0, 0, {"product_id": product.id, "product_uom_qty": 1})
                    ],
                }
            )
            order.foreign_rate = 0.0
            order.foreign_inverse_rate = 0.0
            order.manually_set_rate = False
            order.action_confirm()
            self.assertEqual(order.state, "sale")
