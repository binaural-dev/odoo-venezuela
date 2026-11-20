"""Ticket 16351: el kiosko trabaja con la tasa del día de apertura de su sesión.

Reloj del escenario (``TzBoundaryMixin`` de l10n_ve_accountant): el 10/03
(Caracas) tiene tasa 40; el 11/03 no tiene tasa hasta que la prueba la crea.
"""

from datetime import date

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate
from odoo.addons.l10n_ve_accountant.tests.common_tz_boundary import (
    USD_PER_VEF_INVERSE,
    TzBoundaryMixin,
    freeze_time,
)
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

DAY_1_UTC = "2026-03-10 18:00:00"
DAY_2_UTC = "2026-03-11 14:00:00"


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskSessionRate(TzBoundaryMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._setup_tz_boundary()
        self.config = self.env["pos.config"].create(
            {
                "name": "Kiosko tasa 16351",
                "self_ordering_mode": "kiosk",
                # el kiosko no admite efectivo (los métodos por defecto de la caja)
                # y necesita al menos un método para abrir la sesión
                "payment_method_ids": [Command.set(self._bank_payment_method().ids)],
            }
        )

    def _bank_payment_method(self):
        account = self.env["account.account"].create(
            {
                "name": "Banco kiosko 16351",
                "code": "111016351",
                "account_type": "asset_cash",
                "company_ids": [Command.link(self.company.id)],
            }
        )
        journal = self.env["account.journal"].create(
            {
                "name": "Banco kiosko 16351",
                "code": "BK163",
                "type": "bank",
                "company_id": self.company.id,
                "default_account_id": account.id,
            }
        )
        return self.env["pos.payment.method"].create(
            {"name": "Tarjeta kiosko 16351", "journal_id": journal.id, "company_id": self.company.id}
        )

    def _served_usd_rate(self):
        currencies = self.env["res.currency"]._load_pos_self_data_read(
            self.currency_usd | self.currency_vef, self.config
        )
        return {entry["id"]: entry["rate"] for entry in currencies}[self.currency_usd.id]

    def test_kiosk_does_not_open_without_the_rate_of_the_day(self):
        # assertRaises de Odoo revierte el savepoint, como la petición real:
        # la sesión creada por action_open_wizard no queda
        with freeze_time(DAY_2_UTC), self.assertRaises(UserError) as error:
            self.config.action_open_wizard()
        self.assertIn("no USD rate", str(error.exception))
        self.env.invalidate_all()
        self.assertFalse(self.config.current_session_id)

    def test_kiosk_currencies_keep_the_rate_of_the_session_day(self):
        with freeze_time(DAY_1_UTC):
            self.config.action_open_wizard()
        set_rate(self.env, self.currency_usd, date(2026, 3, 11), self.company, 41.0)
        with freeze_time(DAY_2_UTC):
            self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            self.assertAlmostEqual(self._served_usd_rate(), 1 / USD_PER_VEF_INVERSE, places=12)
            self.assertAlmostEqual(self.config.foreign_rate, USD_PER_VEF_INVERSE, places=4)
