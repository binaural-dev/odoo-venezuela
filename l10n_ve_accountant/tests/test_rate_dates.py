from datetime import datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_accountant.rate_dates import user_local_date


@tagged("post_install", "-at_install", "l10n_ve_accountant_core")
class TestUserLocalDate(TransactionCase):
    """01:00 UTC es todavia el dia anterior en Caracas (UTC-4)."""

    def setUp(self):
        super().setUp()
        self.moment = datetime(2026, 5, 11, 1, 0)

    def test_context_tz_wins(self):
        record = self.env["res.partner"].with_context(tz="America/Caracas")
        self.assertEqual(user_local_date(record, self.moment).isoformat(), "2026-05-10")

    def test_without_context_tz_uses_user_tz(self):
        self.env.user.tz = "America/Caracas"
        record = self.env["res.partner"].with_context(tz=False)
        self.assertEqual(user_local_date(record, self.moment).isoformat(), "2026-05-10")

    def test_without_any_tz_falls_back_to_utc(self):
        self.env.user.tz = False
        record = self.env["res.partner"].with_context(tz=False)
        self.assertEqual(user_local_date(record, self.moment).isoformat(), "2026-05-11")
