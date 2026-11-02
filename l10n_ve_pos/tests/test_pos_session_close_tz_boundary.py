"""Cierre de caja a las 8 pm de Caracas: el asiento de cruce toma la fecha del usuario.

Caracas es UTC-4. A las 8 pm el reloj del servidor (UTC) ya marca el dia siguiente:
``pos.session.stop_at`` y ``pos.payment.create_date`` son Datetime en UTC, y asignarlos
al ``date`` del asiento los trunca a la fecha UTC. ``l10n_ve_rate`` solo acepta la tasa
de la fecha exacta del asiento, asi que el cierre (``close_session_from_ui``) se detenia
con "No hay una tasa asignada para <moneda> al <dia siguiente>" hasta que se cargaba la
tasa de manana.

Estas pruebas FALLAN mientras el asiento use la fecha UTC.
"""

from odoo import fields
from odoo.addons.l10n_ve_accountant.tests.common_tz_boundary import (
    CARACAS_DAY,
    CARACAS_TZ,
    FROZEN_UTC_NOW,
    UTC_DAY,
    freeze_time,
)
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "l10n_ve_pos_tz_boundary", "cross_move")
class TestPosSessionCloseTzBoundary(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Rate = cls.env["res.currency.rate"]
        # solo el dia del usuario tiene tasa: la del dia UTC ("manana") aun no se carga
        Rate.search(
            [
                ("currency_id", "=", cls.foreign_currency.id),
                ("company_id", "=", cls.company.id),
                ("name", ">=", CARACAS_DAY),
            ]
        ).unlink()
        Rate.create(
            {
                "name": CARACAS_DAY,
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
                "rate": 40.0,
            }
        )

        cls.account_real_bank = cls.env["account.account"].create(
            {
                "name": "TZ Real Bank",
                "code": "110001Z",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.real_bank_journal = cls.env["account.journal"].create(
            {
                "name": "TZ Real Bank Journal",
                "type": "bank",
                "code": "RBJZ",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_real_bank.id,
                "inbound_payment_method_line_ids": [
                    (0, 0, {
                        "payment_method_id": manual_in.id,
                        "payment_account_id": cls.account_real_bank.id,
                    })
                ],
                "outbound_payment_method_line_ids": [
                    (0, 0, {
                        "payment_method_id": manual_out.id,
                        "payment_account_id": cls.account_real_bank.id,
                    })
                ],
            }
        )
        cls.cross_account_journal = cls.env["account.journal"].create(
            {
                "name": "TZ Cross Adjustment Journal",
                "type": "general",
                "code": "CAJZ",
                "company_id": cls.company.id,
            }
        )

    def _configure_cross(self, method):
        method.write(
            {
                "cross_account_journal": self.cross_account_journal.id,
                "cross_journal": self.real_bank_journal.id,
            }
        )

    def _cross_moves(self):
        return self.env["account.move"].search(
            [("journal_id", "=", self.cross_account_journal.id), ("company_id", "=", self.company.id)]
        )

    def _new_session(self):
        # contexto como lo manda el cliente web: con la zona horaria del usuario
        return (
            self.env["pos.session"]
            .with_context(tz=CARACAS_TZ)
            .with_company(self.company)
            .create({"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id})
        )

    def test_scenario_is_the_8pm_one(self):
        """Sanity: a esa hora el dia UTC y el del usuario son distintos."""
        with freeze_time(FROZEN_UTC_NOW):
            self.assertEqual(fields.Date.today(), UTC_DAY)
            self.assertEqual(
                fields.Date.context_today(self.env["pos.session"].with_context(tz=CARACAS_TZ)),
                CARACAS_DAY,
            )

    def test_combine_cross_move_dated_with_stop_at_uses_user_day(self):
        """Metodo combinado: el asiento va con ``stop_at`` (UTC) y lleva el dia del usuario."""
        self._configure_cross(self.combined_bank_method)
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            self._create_paid_order(
                session, method=self.combined_bank_method, amount=58.0, name="OL/TZ/COMBINE"
            )
            session.stop_at = fields.Datetime.now()

            session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        self.assertEqual(
            moves.date,
            CARACAS_DAY,
            "El asiento del cierre a las 8 pm de Caracas debe llevar el dia del usuario, "
            "no el dia UTC (que aun no tiene tasa).",
        )

    def test_combine_cross_move_without_stop_at_uses_user_day(self):
        """Sin ``stop_at`` se usa el ahora del servidor: tambien debe pasar a la fecha del usuario."""
        self._configure_cross(self.combined_bank_method)
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            self._create_paid_order(
                session, method=self.combined_bank_method, amount=58.0, name="OL/TZ/COMBINE-NOSTOP"
            )

            session._validate_cross_move()

        self.assertEqual(self._cross_moves().date, CARACAS_DAY)

    def test_split_cross_move_dated_with_payment_create_date_uses_user_day(self):
        """Metodo split: el asiento va con ``pos.payment.create_date`` (UTC)."""
        self._configure_cross(self.split_bank_method)
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            order = self._create_paid_order(
                session, method=self.split_bank_method, amount=58.0, name="OL/TZ/SPLIT"
            )
            # ``create_date`` lo pone la BD (``now()``), que ``freeze_time`` no toca: en
            # produccion el pago se creo a las 8 pm de Caracas y aqui se le da esa hora.
            self.env.cr.execute(
                "UPDATE pos_payment SET create_date = %s WHERE id IN %s",
                (fields.Datetime.now(), tuple(order.payment_ids.ids)),
            )
            order.payment_ids.invalidate_recordset(["create_date"])

            session._validate_cross_move()

        moves = self._cross_moves()
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.date, CARACAS_DAY)


@tagged("post_install", "-at_install", "l10n_ve_pos", "l10n_ve_pos_tz_boundary", "l10n_ve_pos_tz_conversion")
class TestPosSessionConversionDate(TestPosSessionAccountingBase):
    """Conversiones del cierre con un Datetime UTC (``stop_at``, ``payment_date``).

    ``res.currency._convert`` toma la ultima tasa con fecha menor o igual: con un Datetime
    de las 00:30 UTC del dia siguiente y la tasa de manana ya publicada, convertia con
    esa y no con la del dia del usuario (el dia de los asientos del cierre).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Rate = cls.env["res.currency.rate"]
        Rate.search(
            [
                ("currency_id", "=", cls.foreign_currency.id),
                ("company_id", "=", cls.company.id),
                ("name", ">=", CARACAS_DAY),
            ]
        ).unlink()
        for day, rate in ((CARACAS_DAY, 40.0), (UTC_DAY, 50.0)):  # la de manana ya esta publicada
            Rate.create(
                {
                    "name": day,
                    "currency_id": cls.foreign_currency.id,
                    "company_id": cls.company.id,
                    "rate": rate,
                }
            )

    def _new_session(self):
        return (
            self.env["pos.session"]
            .with_context(tz=CARACAS_TZ)
            .with_company(self.company)
            .create({"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id})
        )

    def _converted_at(self, session, amount, day):
        return session.currency_id._convert(
            amount, session.company_id.currency_id, session.company_id, day, round=False
        )

    def _assert_user_day_rate(self, session, actual, amount=100.0):
        expected = self._converted_at(session, amount, CARACAS_DAY)
        at_utc_day = self._converted_at(session, amount, UTC_DAY)
        self.assertNotAlmostEqual(expected, at_utc_day, places=6, msg="las tasas de los dos dias deben diferir")
        self.assertAlmostEqual(
            actual,
            expected,
            places=6,
            msg="convirtio con la tasa de manana (dia UTC) en vez de la del dia del usuario",
        )

    def test_amount_converter_datetime_uses_user_day(self):
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            actual = session._amount_converter(100.0, fields.Datetime.now(), False)
        self._assert_user_day_rate(session, actual)

    def test_amount_converter_date_is_untouched(self):
        """Una fecha (no Datetime) ya es el dia que quiere quien llama: no se toca."""
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            actual = session._amount_converter(100.0, UTC_DAY, False)
        self.assertAlmostEqual(actual, self._converted_at(session, 100.0, UTC_DAY), places=6)

    def test_update_amounts_with_payment_date_uses_user_day(self):
        """El core acumula el cierre con ``_update_amounts(..., payment.payment_date)``."""
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            amounts = session._update_amounts(
                {"amount": 0.0, "amount_converted": 0.0},
                {"amount": 100.0},
                fields.Datetime.now(),
                round=False,
            )
        self._assert_user_day_rate(session, amounts["amount_converted"])

    def test_statement_line_amount_values_use_user_day(self):
        """El extracto de un diario en otra moneda se convierte con ``stop_at`` (UTC)."""
        journal = self.env["account.journal"].create(
            {"name": "TZ Company Currency Journal", "type": "general", "code": "TZCB", "company_id": self.company.id}
        )
        with freeze_time(FROZEN_UTC_NOW):
            session = self._new_session()
            session.stop_at = fields.Datetime.now()
            values = session._prepare_statement_line_amount_values(journal, 100.0)
        self.assertAlmostEqual(values["amount_currency"], 100.0, places=6)
        self._assert_user_day_rate(session, values["amount"])
