from datetime import date
from unittest.mock import patch

import requests

from odoo.addons.l10n_ve_currency_rate_live.models import res_company as currency_res_company
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

        with patch.object(currency_res_company.fields.Date, "context_today", return_value=saturday), patch.object(
            type(self.company),
            "_get_bcv_rate",
        ) as mock_get_rate:
            result = self.company._parse_bcv_data([])

        self.assertEqual(result, {"USD": (1.0, saturday)})
        mock_get_rate.assert_not_called()

    def test_parse_bcv_data_skips_future_published_date(self):
        current_date = date(2026, 6, 23)
        future_date = date(2026, 6, 24)

        with patch.object(currency_res_company.fields.Date, "context_today", return_value=current_date), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, future_date),
        ):
            result = self.company._parse_bcv_data([])

        self.assertEqual(result, {"USD": (1.0, current_date)})

    def test_compute_currency_provider_sets_bcv_for_venezuela(self):
        self.company.country_id = self.country_ve
        self.company._compute_currency_provider()
        self.assertEqual(self.company.currency_provider, "bcv")
