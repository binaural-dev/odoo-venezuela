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

    def test_compute_rate_returns_empty_by_default_when_date_predates_all_rates(self):
        """By default (raise_if_not_found=False), if rate_date is older than
        every recorded rate for this currency/company, compute_rate returns
        {} instead of raising - this is the path taken by automatic callers
        (record defaults, create()-time comparisons, and the ORM re-triggering
        a compute simply because something read the field), none of which can
        meaningfully react to a hard error.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 6, 1), 45.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2020, 1, 1))

        self.assertEqual(result, {})

    def test_compute_rate_raises_when_explicitly_requested_and_date_predates_all_rates(self):
        """With raise_if_not_found=True, the same case above must raise
        UserError instead - reserved for a future call site built
        specifically to let the user act on the error in place.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 6, 1), 45.0)

        with self.assertRaises(UserError):
            self.Rate.compute_rate(
                self.foreign_currency.id, date(2020, 1, 1), raise_if_not_found=True,
            )

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

    def test_compute_rate_returns_empty_by_default_when_no_rate_exists_at_all(self):
        """With no rate at all for this currency/company, there is nothing
        at or before rate_date to use; by default compute_rate returns {}.
        """
        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 1, 1))
        self.assertEqual(result, {})
