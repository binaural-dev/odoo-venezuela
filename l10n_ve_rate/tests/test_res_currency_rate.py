from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestComputeRateFallback(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.currency_id = self.env.ref("base.VEF")
        self.foreign_currency = self.env.ref("base.USD")
        self.Rate = self.env["res.currency.rate"]

    def _create_rate(self, day, rate_value):
        return self.Rate.create({
            "currency_id": self.foreign_currency.id,
            "company_id": self.company.id,
            "name": day,
            "rate": rate_value,
        })

    def test_compute_rate_raises_when_date_predates_all_rates(self):
        """If rate_date is older than every recorded rate for this currency/
        company, there is no earlier rate to fall back to, so compute_rate
        must raise UserError instead of silently returning {} (which callers
        default to a rate of 0).
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 6, 1), 45.0)

        with self.assertRaises(UserError):
            self.Rate.compute_rate(self.foreign_currency.id, date(2020, 1, 1))

    def test_compute_rate_uses_closest_earlier_rate_ignoring_later_ones(self):
        """With no rate for rate_date itself but rates both before and after
        it, compute_rate must use the closest one *before* it - rates dated
        after rate_date are excluded by the domain and must never be picked,
        no matter how close they are.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        closest_before = self._create_rate(date(2023, 6, 1), 45.0)
        self._create_rate(date(2023, 12, 1), 50.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 8, 1))

        self.assertEqual(result["foreign_rate"], closest_before.inverse_company_rate)

    def test_compute_rate_raises_when_no_rate_exists_at_all(self):
        """With no rate at all for this currency/company, there is nothing
        at or before rate_date to use, so compute_rate must raise UserError.
        """
        with self.assertRaises(UserError):
            self.Rate.compute_rate(self.foreign_currency.id, date(2023, 1, 1))
