"""Ticket 16351: la sesión del PdV trabaja con la tasa del día en que se abrió.

Caso de origen (ticket 16201, Grupo Nova): una caja facturó el 03/11 con la tasa
del 02/11 aunque la del 03/11 estaba cargada. La tasa vivía solo en el navegador
(``pos.config.foreign_rate`` se calcula al cargar el PdV) y el popup de apertura
no recarga los datos.

Reloj del escenario (``TzBoundaryMixin``): el 10/03 (Caracas) tiene tasa 40, el
11/03 no tiene tasa hasta que la prueba la crea.
"""

from datetime import date
from unittest.mock import patch

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate
from odoo.addons.l10n_ve_accountant.tests.common_tz_boundary import (
    CARACAS_DAY,
    FROZEN_UTC_NOW,
    USD_PER_VEF_INVERSE,
    TzBoundaryMixin,
    freeze_time,
)
from odoo.addons.point_of_sale.models.pos_session import PosSession as CorePosSession
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

# 10/03 a las 2 pm en Caracas
DAY_1_UTC = "2026-03-10 18:00:00"
# 11/03 a las 10 am en Caracas: el día siguiente
DAY_2_UTC = "2026-03-11 14:00:00"
DAY_2 = date(2026, 3, 11)
DAY_2_RATE = 41.0


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosSessionOpeningRate(TzBoundaryMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._setup_tz_boundary()
        self.config = self.env["pos.config"].create({"name": "Caja tasa 16351"})

    def _new_session(self, config=None):
        return self.env["pos.session"].create(
            {"config_id": (config or self.config).id, "user_id": self.env.uid}
        )

    def _loaded_rates(self, usd_per_vef):
        """Tasas como las manda el navegador: la de la caja y el ``rate`` de
        cada moneda (USD por Bs, el sentido de ``res.currency.rate``)."""
        return {
            "foreign_inverse_rate": 1 / usd_per_vef,
            "currencies": {
                str(self.currency_vef.id): 1.0,
                str(self.currency_usd.id): 1 / usd_per_vef,
            },
        }

    def _served_usd_rate(self):
        """``rate`` de USD que recibe el PdV, con la carga limitada de una caché
        posterior a la última modificación de la moneda."""
        currencies = (
            self.env["res.currency"]
            .with_context(
                pos_last_server_date="2999-01-01 00:00:00", pos_limited_loading=True
            )
            ._load_pos_data_search_read({"product.pricelist": []}, self.config)
        )
        return {entry["id"]: entry["rate"] for entry in currencies}.get(
            self.currency_usd.id
        )

    def test_opening_fixes_the_rate_of_the_day_on_the_session(self):
        with freeze_time(DAY_1_UTC):
            session = self._new_session()
            session.set_opening_control(0, "")

        self.assertEqual(session.state, "opened")
        self.assertEqual(session.foreign_rate_date, CARACAS_DAY)
        self.assertAlmostEqual(self.config.foreign_rate, USD_PER_VEF_INVERSE, places=4)
        self.assertAlmostEqual(
            self.config.foreign_inverse_rate, 1 / USD_PER_VEF_INVERSE, places=12
        )

    def test_session_keeps_its_opening_rate_after_midnight(self):
        """La sesión abierta el 10/03 sigue el 11/03 (ya con tasa 41): la caja,
        la conversión y la moneda que recibe el PdV siguen con la tasa 40."""
        with freeze_time(DAY_1_UTC):
            session = self._new_session()
            session.set_opening_control(0, "")
        set_rate(self.env, self.currency_usd, DAY_2, self.company, DAY_2_RATE)

        with freeze_time(DAY_2_UTC):
            self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            self.assertAlmostEqual(self.config.foreign_rate, USD_PER_VEF_INVERSE, places=4)
            self.assertAlmostEqual(
                self.config._convert(
                    100.0, self.currency_usd, self.currency_vef
                ),
                100.0 * USD_PER_VEF_INVERSE,
                places=2,
            )
            self.assertAlmostEqual(
                self._served_usd_rate(), 1 / USD_PER_VEF_INVERSE, places=12
            )
            self.assertEqual(
                session.check_opening_rate(self._loaded_rates(USD_PER_VEF_INVERSE)),
                {"status": "ok"},
            )

    def test_new_session_takes_the_rate_of_its_own_day(self):
        with freeze_time(DAY_1_UTC):
            self._new_session().set_opening_control(0, "")
        set_rate(self.env, self.currency_usd, DAY_2, self.company, DAY_2_RATE)
        other_config = self.env["pos.config"].create({"name": "Caja 2 tasa 16351"})

        with freeze_time(DAY_2_UTC):
            session = self._new_session(other_config)
            session.set_opening_control(0, "")

            self.assertEqual(session.foreign_rate_date, DAY_2)
            self.assertAlmostEqual(other_config.foreign_rate, DAY_2_RATE, places=4)
            self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            self.assertAlmostEqual(self.config.foreign_rate, USD_PER_VEF_INVERSE, places=4)

    def test_correction_of_the_rate_of_the_same_day_reaches_the_session(self):
        """El BCV corrige la tasa del día con la caja abierta: al recargar, la
        caja recibe la tasa corregida (es la del mismo día)."""
        with freeze_time(DAY_1_UTC):
            self._new_session().set_opening_control(0, "")
            set_rate(self.env, self.currency_usd, CARACAS_DAY, self.company, 40.5)
            self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            self.assertAlmostEqual(self.config.foreign_rate, 40.5, places=4)
            self.assertAlmostEqual(self._served_usd_rate(), 1 / 40.5, places=12)

    def test_register_does_not_open_without_the_rate_of_the_day(self):
        with freeze_time(DAY_2_UTC):
            session = self._new_session()
            with self.assertRaisesRegex(UserError, "no USD rate"):
                session.set_opening_control(0, "")
            self.assertEqual(
                session.check_opening_rate(self._loaded_rates(USD_PER_VEF_INVERSE))[
                    "status"
                ],
                "missing",
            )
        self.assertEqual(session.state, "opening_control")
        self.assertFalse(session.foreign_rate_date)

    def test_opening_detects_a_register_loaded_with_yesterdays_rate(self):
        """La caja se cargó el 10/03 (tasa 40) y se abre el 11/03 sin recargar."""
        with freeze_time(DAY_1_UTC):
            session = self._new_session()
        set_rate(self.env, self.currency_usd, DAY_2, self.company, DAY_2_RATE)

        with freeze_time(DAY_2_UTC):
            self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            result = session.check_opening_rate(self._loaded_rates(USD_PER_VEF_INVERSE))
            self.assertEqual(result["status"], "outdated")
            self.assertEqual(result["currency"], "USD")
            self.assertEqual(
                session.check_opening_rate(self._loaded_rates(DAY_2_RATE)),
                {"status": "ok"},
            )

    def test_opening_detects_an_outdated_currency_rate(self):
        """La caja tiene la tasa del día, pero la moneda (con la que se pasa la
        lista de precios en USD a Bs) quedó con la de la carga anterior."""
        set_rate(self.env, self.currency_usd, DAY_2, self.company, DAY_2_RATE)
        with freeze_time(DAY_2_UTC):
            session = self._new_session()
            loaded = self._loaded_rates(DAY_2_RATE)
            loaded["currencies"][str(self.currency_usd.id)] = 1 / USD_PER_VEF_INVERSE
            self.assertEqual(session.check_opening_rate(loaded)["status"], "outdated")

    def test_currencies_reach_the_pos_on_every_limited_load(self):
        """Una tasa nueva no cambia el ``write_date`` de la moneda: la carga
        limitada debe traer la moneda igual, con la tasa del día."""
        set_rate(self.env, self.currency_usd, DAY_2, self.company, DAY_2_RATE)
        with freeze_time(DAY_2_UTC):
            self._new_session()
            self.assertAlmostEqual(self._served_usd_rate(), 1 / DAY_2_RATE, places=12)

    def test_opening_at_830pm_takes_the_day_of_the_user(self):
        """A las 8:30 pm de Caracas el servidor ya está en el día siguiente: la
        sesión toma el día del usuario (con tasa), no el UTC (sin tasa)."""
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            session.set_opening_control(0, "")
        self.assertEqual(session.foreign_rate_date, CARACAS_DAY)

    def test_rate_date_of_the_register(self):
        with freeze_time(DAY_1_UTC):
            self.assertEqual(self.config._get_pos_rate_date(), CARACAS_DAY)
            session = self._new_session()
            session.set_opening_control(0, "")
        with freeze_time(DAY_2_UTC):
            self.assertEqual(self.config._get_pos_rate_date(), CARACAS_DAY)
            self.assertEqual(session._get_rate_date(), CARACAS_DAY)

    def test_closing_move_of_a_session_after_midnight_takes_its_rate(self):
        """El asiento de la sesión que se cierra el 11/03 lleva la tasa del día
        de la sesión (10/03, 40), la misma con la que se vendió, y no la del
        día del cierre (41). Se aísla el override de ``_create_account_move``:
        el core solo crea el asiento."""
        journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "=", "general")], limit=1
        ) or self.env["account.journal"].create(
            {"name": "POS 16351", "code": "P1635", "type": "general", "company_id": self.company.id}
        )

        def fake_create_account_move(session, *args, **kwargs):
            session.move_id = session.env["account.move"].create(
                {"journal_id": journal.id, "move_type": "entry"}
            )
            return {}

        with freeze_time(DAY_1_UTC):
            session = self._new_session()
            session.set_opening_control(0, "")
        set_rate(self.env, self.currency_usd, DAY_2, self.company, DAY_2_RATE)

        with freeze_time(DAY_2_UTC), patch.object(
            CorePosSession, "_create_account_move", fake_create_account_move
        ):
            self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            session._create_account_move()

        self.assertEqual(session.move_id.date, DAY_2)
        self.assertAlmostEqual(session.move_id.foreign_rate, USD_PER_VEF_INVERSE, places=4)

    def test_check_opening_rate_ignores_malformed_input(self):
        with freeze_time(DAY_1_UTC):
            session = self._new_session()
            for loaded in (
                None,
                "x",
                {"foreign_inverse_rate": "x", "currencies": {"abc": 1, "999999999": "x"}},
                {"foreign_inverse_rate": 1 / USD_PER_VEF_INVERSE, "currencies": ["x"]},
            ):
                self.assertIn(session.check_opening_rate(loaded)["status"], ("ok", "outdated"))
