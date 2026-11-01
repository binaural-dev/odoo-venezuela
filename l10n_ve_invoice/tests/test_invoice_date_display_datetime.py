from datetime import date, datetime as real_datetime
from unittest.mock import patch

import pytz

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_invoice import post_init_hook

# 2026-09-15 02:30 UTC es todavía 2026-09-14 22:30 en Caracas (UTC-4): la
# forma exacta de HD #15954, un documento registrado después de las 20:00.
_FROZEN_UTC_NOW = real_datetime(2026, 9, 15, 2, 30, 0)


class _AnyDatetime(type):
    # fields_temporal hace isinstance(value, datetime) con el nombre ya
    # parcheado: cualquier datetime real tiene que seguir contando.
    def __instancecheck__(cls, obj):
        return isinstance(obj, real_datetime)


class _FrozenDatetime(real_datetime, metaclass=_AnyDatetime):
    """``fields.Datetime.now`` y ``fields.Date.context_today`` llaman a
    ``datetime.now()`` sin argumentos dentro de ``odoo.orm.fields_temporal``."""

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return _FROZEN_UTC_NOW.astimezone(tz)
        return _FROZEN_UTC_NOW


def _frozen():
    return patch("odoo.orm.fields_temporal.datetime", _FrozenDatetime)


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestInvoiceDateDisplayDatetime(TransactionCase):
    """HD #15954: invoice_date_display_datetime toma día y hora de la misma
    zona horaria (la del usuario, como context_today) y, a las 22:30 en
    Caracas, no cae en el día anterior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tz = pytz.timezone("America/Caracas")
        group = cls.env.ref("account.group_account_invoice")
        cls.user_caracas = cls._create_user("ti_15954_caracas", "America/Caracas", group)
        cls.user_no_tz = cls._create_user("ti_15954_no_tz", False, group)

    @classmethod
    def _create_user(cls, login, tz, group):
        return cls.env["res.users"].create({
            "name": login,
            "login": login,
            "email": f"{login}@example.com",
            "group_ids": [(6, 0, [group.id])],
            # Valor explícito: evita el default de tz de l10n_ve_base.
            "tz": tz,
        })

    def _moves_as(self, user):
        return self.env["account.move"].with_user(user).sudo()

    def _local(self, value):
        return pytz.utc.localize(value).astimezone(self.tz)

    def test_user_with_tz_after_8pm_keeps_local_day(self):
        """22:30 del 14/09 en Caracas: queda 14/09 22:30 local (02:30 UTC del 15)."""
        with _frozen():
            value = self._moves_as(self.user_caracas)._get_invoice_date_display_datetime(
                date(2026, 9, 14)
            )
        self.assertEqual(value, real_datetime(2026, 9, 15, 2, 30))
        self.assertEqual(self._local(value).date(), date(2026, 9, 14))

    def test_user_without_tz_uses_utc_for_day_and_time(self):
        """Sin tz, context_today y context_timestamp usan UTC: día y hora
        salen de la misma fuente y el valor es el instante actual."""
        with _frozen():
            moves = self._moves_as(self.user_no_tz)
            value = moves._get_invoice_date_display_datetime(False)
        self.assertEqual(value, _FROZEN_UTC_NOW)

    def test_retroactive_date_keeps_local_time(self):
        """Fecha 10/09 registrada el 14/09 a las 22:30 Caracas: 10/09 22:30 local."""
        with _frozen():
            value = self._moves_as(self.user_caracas)._get_invoice_date_display_datetime(
                date(2026, 9, 10)
            )
        local = self._local(value)
        self.assertEqual(local.date(), date(2026, 9, 10))
        self.assertEqual((local.hour, local.minute), (22, 30))

    def test_missing_date_uses_context_today(self):
        """Sin fecha se usa la de hoy en la tz del usuario: 14/09, no 15/09."""
        with _frozen():
            value = self._moves_as(self.user_caracas)._get_invoice_date_display_datetime(False)
        self.assertEqual(value, _FROZEN_UTC_NOW)
        self.assertEqual(self._local(value).date(), date(2026, 9, 14))

    def test_create_with_default_date(self):
        """create() sin fecha: el default context_today y la hora coinciden."""
        with _frozen():
            move = self._moves_as(self.user_caracas).create({"move_type": "entry"})
        self.assertEqual(move.invoice_date_display, date(2026, 9, 14))
        self.assertEqual(move.invoice_date_display_datetime, _FROZEN_UTC_NOW)

    def test_create_and_write_retroactive(self):
        with _frozen():
            moves = self._moves_as(self.user_caracas)
            move = moves.create({"move_type": "entry", "invoice_date_display": date(2026, 9, 10)})
            self.assertEqual(self._local(move.invoice_date_display_datetime).date(), date(2026, 9, 10))
            move.write({"invoice_date_display": date(2026, 9, 12)})
        local = self._local(move.invoice_date_display_datetime)
        self.assertEqual(local.date(), date(2026, 9, 12))
        self.assertEqual((local.hour, local.minute), (22, 30))

    def test_write_same_date_keeps_time(self):
        """write() no pisa la hora si invoice_date_display no cambia."""
        moves = self._moves_as(self.user_caracas)
        same = moves.create({"move_type": "entry", "invoice_date_display": date(2026, 9, 10)})
        other = moves.create({"move_type": "entry", "invoice_date_display": date(2026, 9, 11)})
        same_before = same.invoice_date_display_datetime
        with _frozen():
            (same | other).write({"invoice_date_display": date(2026, 9, 10)})
        self.assertEqual(same.invoice_date_display_datetime, same_before)
        # other pasa del 11/09 al 10/09: 10/09 22:30 local = 11/09 02:30 UTC.
        self.assertEqual(other.invoice_date_display_datetime, real_datetime(2026, 9, 11, 2, 30))

    def test_write_empty_date_clears_datetime(self):
        move = self._moves_as(self.user_caracas).create(
            {"move_type": "entry", "invoice_date_display": date(2026, 9, 10)}
        )
        move.write({"invoice_date_display": False})
        self.assertFalse(move.invoice_date_display_datetime)

    def test_create_empty_date_leaves_datetime_empty(self):
        """Asiento Diario guardado desde el formulario: el onchange de
        l10n_ve_accountant manda invoice_date_display=False y la fecha-hora
        tiene que quedar vacía, no con la de hoy."""
        with _frozen():
            move = self._moves_as(self.user_caracas).create(
                {"move_type": "entry", "invoice_date_display": False}
            )
        self.assertFalse(move.invoice_date_display)
        self.assertFalse(move.invoice_date_display_datetime)

    def test_post_init_hook_uses_company_tz(self):
        """El hook completa los vacíos con la tz de la compañía."""
        company = self.env.company
        company.partner_id.tz = "America/Caracas"
        move = self.env["account.move"].create(
            {"move_type": "entry", "invoice_date_display": date(2026, 9, 14)}
        )
        self.env.cr.execute(
            "UPDATE account_move SET invoice_date_display_datetime = NULL WHERE id = %s",
            [move.id],
        )
        move.invalidate_recordset(["invoice_date_display_datetime"])
        with _frozen():
            post_init_hook(self.env)
        move.invalidate_recordset(["invoice_date_display_datetime"])
        self.assertEqual(move.invoice_date_display_datetime, _FROZEN_UTC_NOW)
