from datetime import date, datetime

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestLocalDateFromDatetime(TransactionCase):
    """``res.currency.rate._local_date_from_datetime`` is the single place
    that turns a UTC timestamp into "the calendar day it falls on", used by
    every rate lookup (sale orders, POS invoices). Venezuela is UTC-4, so
    from the evening onward the UTC calendar day is already "tomorrow" --
    this must resolve to the real Venezuelan day instead.
    """

    def test_utc_timestamp_already_tomorrow_resolves_to_venezuela_day(self):
        """2026-10-28 02:00 UTC is still 2026-10-27 22:00 in
        America/Caracas -- the exact "UTC already tomorrow" window reported
        against production."""
        self.env.user.tz = False
        Rate = self.env["res.currency.rate"]

        result = Rate._local_date_from_datetime(datetime(2026, 10, 28, 2, 0, 0))

        self.assertEqual(result, date(2026, 10, 27))

    def test_utc_timestamp_safely_within_the_day_is_unchanged(self):
        """A timestamp comfortably inside the UTC day (not near midnight)
        still falls on the same Venezuelan calendar day."""
        self.env.user.tz = False
        Rate = self.env["res.currency.rate"]

        result = Rate._local_date_from_datetime(datetime(2026, 10, 27, 14, 0, 0))

        self.assertEqual(result, date(2026, 10, 27))

    def test_falls_back_to_venezuela_when_user_has_no_tz(self):
        """No tz configured anywhere (the common case for a POS/cashier
        account) must fall back to America/Caracas, never UTC."""
        self.env.user.tz = False
        Rate = self.env["res.currency.rate"]

        result = Rate._local_date_from_datetime(
            datetime(2026, 10, 28, 2, 0, 0), tz_name=None
        )

        self.assertEqual(result, date(2026, 10, 27))

    def test_explicit_tz_name_is_honored(self):
        """An explicit tz (e.g. the order's own cashier) takes precedence
        over the Venezuela fallback."""
        Rate = self.env["res.currency.rate"]

        # UTC+9 (Asia/Tokyo): 2026-10-27 20:00 UTC is already 2026-10-28
        # there, the mirror case of the Venezuela bug.
        result = Rate._local_date_from_datetime(
            datetime(2026, 10, 27, 20, 0, 0), tz_name="Asia/Tokyo"
        )

        self.assertEqual(result, date(2026, 10, 28))

    def test_falsy_value_is_returned_as_is(self):
        Rate = self.env["res.currency.rate"]
        self.assertFalse(Rate._local_date_from_datetime(False))
