from datetime import date

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

    def test_compute_rate_returns_oldest_rate_when_date_predates_all_rates(self):
        """If rate_date is older than any recorded rate for this currency/company,
        compute_rate must fall back to the oldest rate on record instead of
        returning {} - a stale rate is safer than the 0 that callers default to
        when the dict comes back empty.
        """
        oldest = self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 6, 1), 45.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2020, 1, 1))

        self.assertTrue(result, "compute_rate should not return an empty dict.")
        self.assertEqual(
            result["foreign_rate"], oldest.inverse_company_rate,
            "Should fall back to the oldest rate on record (USD uses inverse_company_rate).",
        )

    def test_compute_rate_still_prefers_closest_rate_at_or_before_date(self):
        """The fallback must not interfere with the normal path: a date that
        does have a matching rate at-or-before it should still resolve to the
        closest one, not the oldest.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        closest = self._create_rate(date(2023, 6, 1), 45.0)
        self._create_rate(date(2023, 12, 1), 50.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 8, 1))

        self.assertEqual(result["foreign_rate"], closest.inverse_company_rate)

    def test_compute_rate_returns_empty_when_no_rate_exists_at_all(self):
        """With no rate at all for this currency/company, both the primary
        search and the fallback search find nothing, so compute_rate still
        returns {} - this is not a case the fallback is meant to cover.
        """
        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 1, 1))
        self.assertEqual(result, {})
