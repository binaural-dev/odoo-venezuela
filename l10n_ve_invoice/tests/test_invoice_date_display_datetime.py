from datetime import date, datetime
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestInvoiceDateDisplayDatetime(TransactionCase):
    """HD #15992: invoice_date_display_datetime debe caer en el día de
    invoice_date_display también cuando se registra después de las 20:00 en
    Venezuela (UTC-4), cuando en UTC ya es el día siguiente."""

    def setUp(self):
        super().setUp()
        self.move_model = self.env["account.move"]
        self.tz = pytz.timezone("America/Caracas")

    def _local(self, value):
        return pytz.utc.localize(value).astimezone(self.tz)

    def test_after_8pm_keeps_invoice_day(self):
        """30/09 a las 20:41 en Caracas = 01/10 00:41 UTC: no debe quedar el 29/09."""
        value = self.move_model._build_invoice_date_display_datetime(
            date(2026, 9, 30), self.tz, now=datetime(2026, 10, 1, 0, 41, 4)
        )
        self.assertEqual(value, datetime(2026, 10, 1, 0, 41, 4))
        self.assertEqual(self._local(value).date(), date(2026, 9, 30))

    def test_before_8pm(self):
        """15/10 a las 12:10 en Caracas = 16:10 UTC del mismo día."""
        value = self.move_model._build_invoice_date_display_datetime(
            date(2026, 10, 15), self.tz, now=datetime(2026, 10, 15, 16, 10, 0)
        )
        self.assertEqual(value, datetime(2026, 10, 15, 16, 10, 0))

    def test_invoice_date_different_from_today(self):
        """Factura con fecha 14/10 registrada el 19/10 a las 21:30 Caracas."""
        value = self.move_model._build_invoice_date_display_datetime(
            date(2026, 10, 14), self.tz, now=datetime(2026, 10, 20, 1, 30, 0)
        )
        local = self._local(value)
        self.assertEqual(local.date(), date(2026, 10, 14))
        self.assertEqual((local.hour, local.minute), (21, 30))

    def test_empty_date(self):
        self.assertFalse(
            self.move_model._build_invoice_date_display_datetime(False, self.tz)
        )

    def test_tz_falls_back_to_caracas(self):
        company = self.env.company
        company.partner_id.tz = False
        self.env.user.tz = False
        self.assertEqual(
            self.move_model._get_invoice_date_display_tz(company).zone,
            "America/Caracas",
        )

    def test_create_and_write_after_8pm(self):
        """create() y write() usan la hora local de la compañía."""
        self.env.company.partner_id.tz = "America/Caracas"
        frozen = datetime(2026, 10, 1, 0, 41, 4)
        with patch.object(fields.Datetime, "now", return_value=frozen):
            move = self.move_model.create(
                {"move_type": "entry", "invoice_date_display": date(2026, 9, 30)}
            )
            self.assertEqual(
                self._local(move.invoice_date_display_datetime).date(),
                date(2026, 9, 30),
            )
            move.write({"invoice_date_display": date(2026, 9, 29)})
            self.assertEqual(
                self._local(move.invoice_date_display_datetime).date(),
                date(2026, 9, 29),
            )
