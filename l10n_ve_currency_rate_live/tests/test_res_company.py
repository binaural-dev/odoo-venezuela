from datetime import date
from unittest.mock import patch

import requests

from odoo.addons.l10n_ve_currency_rate_live.models import (
    res_company as currency_res_company,
)
from odoo.tests import TransactionCase, tagged


class MockResponse:
    def __init__(self, text="", json_data=None, status_code=200):
        self.text = text
        self._json_data = json_data or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


@tagged("post_install", "-at_install", "l10n_ve_currency_rate_live", "res_company")
class TestCurrencyRateLiveResCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.country_ve = cls.env.ref("base.ve")

    def test_scrape_bcv_rate_success(self):
        html = """
            <div id="dolar">36,12 USD</div>
            <span class="date-display-single" content="2026-06-23T00:00:00-04:00"></span>
        """

        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ) as mock_get:
            rate, published_date = self.company._scrape_bcv_rate()

        self.assertEqual(rate, 36.12)
        self.assertEqual(published_date, date(2026, 6, 23))
        self.assertEqual(mock_get.call_count, 1)

    def test_scrape_bcv_rate_retries_on_timeout(self):
        with patch.object(
            currency_res_company.requests,
            "get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ) as mock_get:
            rate, published_date = self.company._scrape_bcv_rate()

        self.assertIsNone(rate)
        self.assertIsNone(published_date)
        self.assertEqual(mock_get.call_count, currency_res_company.SOURCE_MAX_ATTEMPTS)

    def test_scrape_bcv_rate_retries_when_html_has_no_dolar(self):
        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text="<html></html>"),
        ) as mock_get:
            rate, published_date = self.company._scrape_bcv_rate()

        self.assertIsNone(rate)
        self.assertIsNone(published_date)
        self.assertEqual(mock_get.call_count, currency_res_company.SOURCE_MAX_ATTEMPTS)

    def test_parse_bcv_data_skips_weekend_when_habil_days_enabled(self):
        saturday = date(2026, 6, 20)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=saturday
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
        ) as mock_get_rate:
            result = self.company._parse_bcv_data([])

        self.assertEqual(result, {"USD": (1.0, saturday)})
        mock_get_rate.assert_not_called()

    def test_bcv_update_window_includes_seven_oclock(self):
        current_time = currency_res_company.datetime(2026, 6, 23, 7, 0, 0)

        self.assertTrue(self.company._is_bcv_update_window(current_time))

    def test_bcv_update_window_excludes_after_seven_oclock(self):
        current_time = currency_res_company.datetime(2026, 6, 23, 7, 1, 0)

        self.assertFalse(self.company._is_bcv_update_window(current_time))

    def test_get_next_bcv_retry_time_returns_next_half_hour_slot(self):
        current_time = currency_res_company.datetime(2026, 6, 23, 5, 5, 0)

        retry_at = self.company._get_next_bcv_retry_time(current_time)

        self.assertEqual(retry_at, currency_res_company.datetime(2026, 6, 23, 5, 30, 0))

    def test_get_next_bcv_retry_time_aligns_to_next_slot_boundary(self):
        current_time = currency_res_company.datetime(2026, 6, 23, 5, 31, 0)

        retry_at = self.company._get_next_bcv_retry_time(current_time)

        self.assertEqual(retry_at, currency_res_company.datetime(2026, 6, 23, 6, 0, 0))

    def test_get_next_bcv_retry_time_stops_after_window_end(self):
        current_time = currency_res_company.datetime(2026, 6, 23, 7, 0, 0)

        retry_at = self.company._get_next_bcv_retry_time(current_time)

        self.assertIsNone(retry_at)

    def test_parse_bcv_data_skips_future_published_date(self):
        current_date = date(2026, 6, 23)
        future_date = date(2026, 6, 24)
        self.company.can_update_habil_days = False

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=current_date
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, future_date),
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(result, {"USD": (1.0, current_date)})

    def test_parse_bcv_data_accepts_future_published_date_when_habil_days_enabled(self):
        current_date = date(2026, 6, 23)
        future_date = date(2026, 6, 24)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=current_date
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, future_date),
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(
            result, {"USD": (1.0, current_date), "VEF": (36.12, current_date)}
        )

    def test_parse_bcv_data_accepts_last_available_rate_from_source_when_habil_days_disabled(
        self,
    ):
        current_date = date(2026, 6, 23)
        previous_date = date(2026, 6, 20)
        self.company.can_update_habil_days = False

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=current_date
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, previous_date),
        ), patch.object(
            type(self.company),
            "_get_last_system_rate",
            return_value=35.5,
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(
            result, {"USD": (1.0, current_date), "VEF": (36.12, current_date)}
        )

    def test_parse_bcv_data_skips_last_available_rate_when_habil_days_enabled(self):
        current_date = date(2026, 6, 23)
        previous_date = date(2026, 6, 20)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=current_date
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, previous_date),
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(result, {"USD": (1.0, current_date)})

    def test_parse_bcv_data_uses_last_system_rate_when_future_rate_arrives_and_habil_days_disabled(
        self,
    ):
        current_date = date(2026, 6, 29)
        future_date = date(2026, 6, 30)
        self.company.can_update_habil_days = False

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=current_date
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(623.023, future_date),
        ), patch.object(
            type(self.company),
            "_get_last_system_rate",
            return_value=622.2135,
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(
            result, {"USD": (1.0, current_date), "VEF": (622.2135, current_date)}
        )

    def test_parse_bcv_data_uses_last_system_rate_when_no_source_rate_and_habil_days_disabled(
        self,
    ):
        current_date = date(2026, 6, 29)
        self.company.can_update_habil_days = False

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=current_date
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(None, None),
        ), patch.object(
            type(self.company),
            "_get_last_system_rate",
            return_value=622.2135,
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(
            result, {"USD": (1.0, current_date), "VEF": (622.2135, current_date)}
        )

    def test_get_bcv_rate_falls_back_to_scraping_when_api_date_is_stale(self):
        current_date = date(2026, 6, 23)

        with patch.object(
            type(self.company),
            "_get_bcv_rate_from_api",
            return_value=(None, None),
        ) as mock_api, patch.object(
            type(self.company),
            "_scrape_bcv_rate",
            return_value=(36.12, current_date),
        ) as mock_scrape:
            rate, published_date = self.company._get_bcv_rate(
                expected_date=current_date
            )

        self.assertEqual(rate, 36.12)
        self.assertEqual(published_date, current_date)
        mock_api.assert_called_once_with(expected_date=current_date)
        mock_scrape.assert_called_once()

    def test_run_update_bcv_currency_does_not_abort_on_company_error(self):
        with patch.object(
            type(self.company),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            type(self.company),
            "search",
            return_value=self.company,
        ), patch.object(
            type(self.env["res.currency"]),
            "search",
            return_value=self.company.currency_id,
        ), patch.object(
            type(self.env["res.currency.rate"]),
            "search_count",
            return_value=0,
        ), patch.object(
            type(self.company),
            "update_currency_rates",
            side_effect=RuntimeError("boom"),
        ):
            self.company.run_update_bcv_currency()

    def test_run_update_bcv_currency_swallows_unexpected_errors(self):
        with patch.object(
            type(self.company),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            type(self.company),
            "search",
            side_effect=RuntimeError("search failed"),
        ):
            self.company.run_update_bcv_currency()

    def test_run_update_bcv_currency_schedules_retry_when_rate_is_still_missing(self):
        retry_at = currency_res_company.datetime(2026, 6, 23, 5, 30, 0)

        with patch.object(
            type(self.company),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            type(self.company),
            "search",
            return_value=self.company,
        ), patch.object(
            type(self.env["res.currency"]),
            "search",
            return_value=self.company.currency_id,
        ), patch.object(
            type(self.env["res.currency.rate"]),
            "search_count",
            side_effect=[0, 0],
        ), patch.object(
            type(self.company),
            "_get_next_bcv_retry_time",
            return_value=retry_at,
        ), patch.object(
            type(self.company),
            "_schedule_bcv_retry",
            return_value=True,
        ) as mock_schedule:
            self.company.run_update_bcv_currency()

        mock_schedule.assert_called_once_with(retry_at)

    def test_run_update_bcv_currency_does_not_schedule_retry_when_rate_is_created(self):
        with patch.object(
            type(self.company),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            type(self.company),
            "search",
            return_value=self.company,
        ), patch.object(
            type(self.env["res.currency"]),
            "search",
            return_value=self.company.currency_id,
        ), patch.object(
            type(self.env["res.currency.rate"]),
            "search_count",
            side_effect=[0, 1],
        ), patch.object(
            type(self.company),
            "_schedule_bcv_retry",
        ) as mock_schedule:
            self.company.run_update_bcv_currency()

        mock_schedule.assert_not_called()

    def test_compute_currency_provider_sets_bcv_for_venezuela(self):
        self.company.country_id = self.country_ve
        self.company._compute_currency_provider()
        self.assertEqual(self.company.currency_provider, "bcv")
