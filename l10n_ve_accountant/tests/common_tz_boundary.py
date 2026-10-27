"""Fixtures para reproducir el desfase UTC / hora de Caracas al crear documentos.

Caracas es UTC-4 y no tiene horario de verano. A las 8:00 pm de Caracas el reloj
del servidor (UTC) ya marca el dia siguiente: el usuario ve "hoy" pero cualquier
codigo que use ``fields.Date.today()`` o ``date_order.date()`` (Datetime en UTC)
busca la tasa de "manana", que aun no existe, y `compute_rate` lanza UserError.
"""

from datetime import date

from freezegun import freeze_time  # noqa: F401  (se reexporta para las pruebas)

from odoo import fields

from .common_rates import set_rate

CARACAS_TZ = "America/Caracas"

# 2026-03-11 00:30 UTC == 2026-03-10 20:30 en Caracas.
FROZEN_UTC_NOW = "2026-03-11 00:30:00"
CARACAS_DAY = date(2026, 3, 10)  # lo que ve el usuario
UTC_DAY = date(2026, 3, 11)  # lo que ve el servidor

USD_PER_VEF_INVERSE = 40.0  # 1 USD = 40 VEF en la tasa del dia de Caracas


class TzBoundaryMixin:
    """Prepara compania VEF/USD, usuario en Caracas y tasas solo hasta CARACAS_DAY.

    Se mezcla en un ``TransactionCase`` y se llama ``_setup_tz_boundary()`` desde
    ``setUp``. Deja sin tasa a ``UTC_DAY``: es el escenario de las 8 pm.
    """

    def _setup_tz_boundary(self):
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef.active = True
        self.currency_usd.active = True
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
            }
        )
        self.env.user.write(
            {
                "tz": CARACAS_TZ,
                "company_ids": [(4, self.company.id)],
                "company_id": self.company.id,
            }
        )
        # contexto como lo manda el cliente web: con la zona horaria del usuario
        self.env = self.env(context=dict(self.env.context, tz=CARACAS_TZ))

        Rate = self.env["res.currency.rate"].sudo()
        # el dia del usuario y el anterior tienen tasa; el dia UTC no
        Rate.search(
            [
                ("currency_id", "=", self.currency_usd.id),
                ("company_id", "=", self.company.id),
                ("name", ">=", CARACAS_DAY),
            ]
        ).unlink()
        set_rate(
            self.env, self.currency_usd, date(2026, 3, 9), self.company, 39.0
        )
        self.rate_caracas_day = set_rate(
            self.env,
            self.currency_usd,
            CARACAS_DAY,
            self.company,
            USD_PER_VEF_INVERSE,
        )

    def assertCaracasDay(self):
        """Sanity: el escenario debe ser realmente el de las 8 pm."""
        now_utc = fields.Datetime.now()
        assert now_utc.date() == UTC_DAY, now_utc
        assert fields.Date.context_today(self.env.user) == CARACAS_DAY
