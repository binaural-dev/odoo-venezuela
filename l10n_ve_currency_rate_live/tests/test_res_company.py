import logging
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

        # Ensure all BCV-scraped currencies exist and are active in the
        # test database.  The base ``res_currency_data.xml`` creates them
        # with ``active=False``, and the enterprise ``update_currency_rates()``
        # passes a recordset of *only active* currencies to ``_parse_bcv_data()``.
        Currency = cls.env["res.currency"]
        for code in ("EUR", "CNY", "TRY", "RUB", "USD"):
            currency = Currency.with_context(active_test=False).search(
                [("name", "=", code)], limit=1,
            )
            if not currency:
                currency = Currency.create({
                    "name": code,
                    "symbol": code[:3],
                    "active": True,
                })
            elif not currency.active:
                currency.active = True

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

    def test_parse_bcv_data_accepts_future_rate_on_weekend_when_habil_days_enabled(
        self,
    ):
        saturday = date(2026, 6, 20)
        monday = date(2026, 6, 22)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=saturday
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, monday),
        ) as mock_get_rate:
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

        self.assertEqual(result, {"USD": (1.0, saturday), "VEF": (36.12, saturday)})
        mock_get_rate.assert_called_once_with(expected_date=saturday)

    def test_parse_bcv_data_accepts_last_available_rate_on_weekend_when_habil_days_disabled(
        self,
    ):
        saturday = date(2026, 6, 20)
        friday = date(2026, 6, 19)
        self.company.can_update_habil_days = False

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=saturday
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(36.12, friday),
        ) as mock_get_rate:
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

        self.assertEqual(result, {"USD": (1.0, saturday), "VEF": (36.12, saturday)})
        mock_get_rate.assert_called_once_with(expected_date=saturday)

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
        ), patch.object(
            type(self.company),
            "_get_last_system_rate",
            return_value=None,
        ):
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

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
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

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
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

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
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

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
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

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
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

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

    # ==================================================================
    # Multi-currency: _get_bcv_currency_rates
    # ==================================================================

    def _bcv_multi_html(self, overrides=None):
        """Build a realistic BCV HTML snippet with the given overrides.

        ``overrides`` is a dict ``{currency_code: (html_id, value)}``.
        """
        defaults = {
            "EUR": ("euro", " 830,63195644"),
            "CNY": ("yuan", " 107,21730826"),
            "TRY": ("lira", " 15,43986653"),
            "RUB": ("rublo", " 9,36394988"),
            "USD": ("dolar", " 725,74700000"),
        }
        if overrides:
            defaults.update(overrides)

        divs = ""
        for code, (html_id, val) in defaults.items():
            divs += (
                f'<div id="{html_id}"><strong class="strong-tb">{val}</strong></div>\n'
            )
        return (
            divs
            + '<span class="date-display-single" '
            + 'content="2026-07-15T00:00:00-04:00"></span>'
        )

    def test_get_bcv_currency_rates_all_active(self):
        """T5: Todas las monedas activas → todas parseadas correctamente."""
        html = self._bcv_multi_html()

        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ) as mock_get:
            result = self.company._get_bcv_currency_rates(
                ["EUR", "CNY", "TRY", "RUB", "USD"],
            )

        self.assertEqual(len(result), 5)
        self.assertAlmostEqual(result["EUR"][0], 830.63195644)
        self.assertAlmostEqual(result["CNY"][0], 107.21730826)
        self.assertAlmostEqual(result["TRY"][0], 15.43986653)
        self.assertAlmostEqual(result["RUB"][0], 9.36394988)
        self.assertAlmostEqual(result["USD"][0], 725.747)
        self.assertEqual(result["EUR"][1], date(2026, 7, 15))
        self.assertEqual(result["CNY"][1], date(2026, 7, 15))
        self.assertEqual(mock_get.call_count, 1)

    def test_get_bcv_currency_rates_partial_active(self):
        """T6: Solo EUR+USD activas → solo esas retornadas."""
        html = self._bcv_multi_html()

        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ) as mock_get:
            result = self.company._get_bcv_currency_rates(["EUR", "USD"])

        self.assertEqual(len(result), 2)
        self.assertIn("EUR", result)
        self.assertIn("USD", result)
        self.assertNotIn("CNY", result)
        self.assertNotIn("TRY", result)
        self.assertNotIn("RUB", result)
        self.assertEqual(mock_get.call_count, 1)

    def test_get_bcv_currency_rates_none_active(self):
        """T7: Ninguna moneda activa → dict vacío."""
        result = self.company._get_bcv_currency_rates([])
        self.assertEqual(result, {})

    def test_get_bcv_currency_rates_http_error(self):
        """T8: Timeout → dict vacío + sin excepción."""
        with patch.object(
            currency_res_company.requests,
            "get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ) as mock_get:
            result = self.company._get_bcv_currency_rates(["EUR", "USD"])

        self.assertEqual(result, {})
        # Should have retried SOURCE_MAX_ATTEMPTS times
        self.assertEqual(
            mock_get.call_count,
            currency_res_company.SOURCE_MAX_ATTEMPTS,
        )

    def test_get_bcv_currency_rates_missing_element(self):
        """T9: HTML sin #euro → EUR omitido, demás OK."""
        html = self._bcv_multi_html({"EUR": ("euro", "")})
        # Remove the euro div entirely
        html = html.replace('<div id="euro"><strong class="strong-tb"> </strong></div>\n', '')

        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ):
            result = self.company._get_bcv_currency_rates(
                ["EUR", "CNY", "TRY", "RUB", "USD"],
            )

        self.assertNotIn("EUR", result)
        self.assertIn("CNY", result)
        self.assertIn("USD", result)

    def test_get_bcv_currency_rates_negative_value(self):
        """T10: Valor EUR negativo → EUR omitido."""
        html = self._bcv_multi_html({"EUR": ("euro", " -1,00")})

        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ):
            result = self.company._get_bcv_currency_rates(["EUR", "USD"])

        self.assertNotIn("EUR", result)
        self.assertIn("USD", result)

    # ==================================================================
    # Multi-currency: _parse_bcv_data integration
    # ==================================================================

    def test_parse_bcv_data_multi_currency(self):
        """T11: USD (DolarAPI) + EUR/CNY activas → normalizadas contra USD."""
        current_date = date(2026, 7, 15)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date,
            "context_today",
            return_value=current_date,
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(725.747, current_date),
        ), patch.object(
            type(self.company),
            "_get_bcv_currency_rates",
            return_value={
                "EUR": (830.63195644, current_date),
                "CNY": (107.21730826, current_date),
            },
        ):
            result = self.company._parse_bcv_data(
                self.env["res.currency"].search(
                    [("name", "in", ["EUR", "CNY", "USD"])],
                ),
            )

        self.assertIn("EUR", result)
        self.assertIn("CNY", result)
        self.assertIn("VEF", result)
        self.assertIn("USD", result)

        # EUR expressed as "EUR per 1 USD" = USD_VEF / EUR_VEF
        # = 725.747 / 830.63195644 = 0.8737
        self.assertAlmostEqual(result["EUR"][0], 0.8737, places=4)
        # CNY expressed as "CNY per 1 USD" = USD_VEF / CNY_VEF
        # = 725.747 / 107.21730826 = 6.7689
        self.assertAlmostEqual(result["CNY"][0], 6.7689, places=4)
        self.assertEqual(result["EUR"][1], current_date)
        self.assertEqual(result["CNY"][1], current_date)

    def test_parse_bcv_data_only_usd_active(self):
        """T12: Solo USD activa → comportamiento original."""
        current_date = date(2026, 7, 15)

        with patch.object(
            currency_res_company.fields.Date,
            "context_today",
            return_value=current_date,
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(725.747, current_date),
        ):
            result = self.company._parse_bcv_data(
                self.env["res.currency"].search(
                    [("name", "=", "USD")],
                ),
            )

        self.assertEqual(
            result,
            {"USD": (1.0, current_date), "VEF": (725.747, current_date)},
        )

    def test_parse_bcv_data_dolarapi_fallback_bcv_multi(self):
        """T13: DolarAPI falla, USD cae a scraping BCV, EUR+CNY vía scraping multi-moneda."""
        current_date = date(2026, 7, 15)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date,
            "context_today",
            return_value=current_date,
        ), patch.object(
            type(self.company),
            "_get_bcv_rate_from_api",
            return_value=(None, None),
        ) as mock_api, patch.object(
            type(self.company),
            "_scrape_bcv_rate",
            return_value=(725.747, current_date),
        ) as mock_scrape, patch.object(
            type(self.company),
            "_get_bcv_currency_rates",
            return_value={
                "EUR": (830.63195644, current_date),
                "CNY": (107.21730826, current_date),
            },
        ):
            result = self.company._parse_bcv_data(
                self.env["res.currency"].search(
                    [("name", "in", ["EUR", "CNY", "USD"])],
                ),
            )

        mock_api.assert_called_once()
        mock_scrape.assert_called_once()
        self.assertEqual(result["USD"], (1.0, current_date))
        self.assertIn("EUR", result)
        self.assertIn("CNY", result)
        self.assertIn("VEF", result)

    def test_parse_bcv_data_all_fail_fallback_vef(self):
        """T14: DolarAPI + BCV fallan → fallback VEF."""
        current_date = date(2026, 7, 15)
        self.company.can_update_habil_days = False

        with patch.object(
            currency_res_company.fields.Date,
            "context_today",
            return_value=current_date,
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(None, None),
        ), patch.object(
            type(self.company),
            "_get_last_system_rate",
            return_value=622.2135,
        ):
            result = self.company._parse_bcv_data(
                self.env["res.currency"].search(
                    [("name", "in", ["EUR", "CNY", "USD"])],
                ),
            )

        self.assertEqual(
            result,
            {"USD": (1.0, current_date), "VEF": (622.2135, current_date)},
        )

    def test_parse_bcv_data_secondary_currency_falls_back_to_last_system_rate(self):
        """EUR scraping fails but a stored rate exists → fallback is used instead of skipping."""
        current_date = date(2026, 7, 15)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date,
            "context_today",
            return_value=current_date,
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(725.747, current_date),
        ), patch.object(
            type(self.company),
            "_get_bcv_currency_rates",
            return_value={},
        ), patch.object(
            type(self.company),
            "_get_last_system_rate_for_currency",
            return_value=0.8737,
        ) as mock_fallback:
            result = self.company._parse_bcv_data(
                self.env["res.currency"].search(
                    [("name", "in", ["EUR", "USD"])],
                ),
            )

        mock_fallback.assert_called_once_with("EUR", current_date)
        self.assertEqual(result["EUR"], (0.8737, current_date))

    def test_parse_bcv_data_secondary_currency_skipped_without_fallback(self):
        """EUR scraping fails and there is no stored rate → EUR is omitted, not crashed."""
        current_date = date(2026, 7, 15)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date,
            "context_today",
            return_value=current_date,
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
            return_value=(725.747, current_date),
        ), patch.object(
            type(self.company),
            "_get_bcv_currency_rates",
            return_value={},
        ), patch.object(
            type(self.company),
            "_get_last_system_rate_for_currency",
            return_value=None,
        ):
            result = self.company._parse_bcv_data(
                self.env["res.currency"].search(
                    [("name", "in", ["EUR", "USD"])],
                ),
            )

        self.assertNotIn("EUR", result)

    def test_compute_currency_provider_sets_bcv_for_venezuela(self):
        self.company.country_id = self.country_ve
        self.company._compute_currency_provider()
        self.assertEqual(self.company.currency_provider, "bcv")

    # ==================================================================
    # T17: _bcv_http_get — TLS hardening
    # ==================================================================

    def test_bcv_http_get_verifies_tls_by_default(self):
        """_bcv_http_get calls requests.get with verify=True (default)."""
        mock_response = MockResponse(text="ok")
        with patch.object(
            currency_res_company.requests, "get", return_value=mock_response,
        ) as mock_get:
            result = self.company._bcv_http_get(
                currency_res_company.BCV_URL, timeout=30,
            )

        self.assertIs(result, mock_response)
        mock_get.assert_called_once_with(
            currency_res_company.BCV_URL,
            timeout=30,
            headers=currency_res_company.BCV_HEADERS,
        )
        # verify is not passed → defaults to True in requests.get
        self.assertNotIn("verify", mock_get.call_args.kwargs)

    def test_bcv_http_get_falls_back_on_ssl_error(self):
        """_bcv_http_get retries with verify=False when SSLError occurs."""
        mock_response = MockResponse(text="ok")
        ssl_error = requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED")
        with patch.object(
            currency_res_company.requests, "get",
            side_effect=[ssl_error, mock_response],
        ) as mock_get, self.assertLogs(
            "odoo.addons.l10n_ve_currency_rate_live.models.res_company",
            level=logging.ERROR,
        ) as cm:
            result = self.company._bcv_http_get(
                currency_res_company.BCV_URL, timeout=30,
            )

        self.assertIs(result, mock_response)
        self.assertEqual(mock_get.call_count, 2)
        # Second call must use verify=False
        second_call = mock_get.call_args_list[1]
        self.assertFalse(second_call.kwargs.get("verify", True))
        # Error logged
        self.assertTrue(
            any("TLS certificate verification failed" in msg for msg in cm.output)
        )

    def test_bcv_http_get_propagates_non_ssl_errors(self):
        """_bcv_http_get does NOT swallow non-SSL RequestExceptions."""
        timeout_err = requests.exceptions.Timeout("timed out")
        with patch.object(
            currency_res_company.requests, "get",
            side_effect=timeout_err,
        ):
            with self.assertRaises(requests.exceptions.Timeout):
                self.company._bcv_http_get(
                    currency_res_company.BCV_URL, timeout=30,
                )

    # ==================================================================
    # T18: _normalize_currency_rate — logging for silent omissions
    # ==================================================================

    def test_normalize_currency_rate_logs_when_usd_missing(self):
        """Warning logged when USD/VEF reference rate is missing from result."""
        result = {}  # No VEF entry
        with self.assertLogs(
            "odoo.addons.l10n_ve_currency_rate_live.models.res_company",
            level=logging.WARNING,
        ) as cm:
            self.company._normalize_currency_rate(result, "EUR", 830.0, date(2026, 7, 15))

        self.assertNotIn("EUR", result)
        self.assertTrue(
            any("USD/VEF reference rate is missing" in msg for msg in cm.output)
        )

    def test_normalize_currency_rate_logs_when_vef_rate_zero(self):
        """Warning logged when VEF rate for the currency is zero."""
        result = {"VEF": (725.0, date(2026, 7, 15))}
        with self.assertLogs(
            "odoo.addons.l10n_ve_currency_rate_live.models.res_company",
            level=logging.WARNING,
        ) as cm:
            self.company._normalize_currency_rate(result, "EUR", 0.0, date(2026, 7, 15))

        self.assertNotIn("EUR", result)
        self.assertTrue(
            any("scraped VEF rate is missing or zero" in msg for msg in cm.output)
        )

    def test_normalize_currency_rate_succeeds_with_valid_inputs(self):
        """EUR rate computed correctly from USD/VEF and EUR/VEF."""
        result = {"VEF": (725.747, date(2026, 7, 15))}
        self.company._normalize_currency_rate(result, "EUR", 830.63, date(2026, 7, 15))

        self.assertIn("EUR", result)
        self.assertAlmostEqual(result["EUR"][0], 725.747 / 830.63, places=4)
        self.assertEqual(result["EUR"][1], date(2026, 7, 15))

    def test_normalize_currency_rate_handles_tuple_vef(self):
        """VEF entry as tuple is correctly unwrapped."""
        result = {"VEF": (725.747, date(2026, 7, 15))}
        self.company._normalize_currency_rate(result, "EUR", 830.63, date(2026, 7, 15))

        self.assertIn("EUR", result)
        self.assertAlmostEqual(result["EUR"][0], 725.747 / 830.63, places=4)

    # ==================================================================
    # T19: run_update_bcv_currency — company failure isolation
    # ==================================================================

    def test_run_update_bcv_currency_isolates_company_failures(self):
        """One company failing does not prevent the other from being updated."""
        comp_a = self.company
        comp_b = self.env["res.company"].create({"name": "BCV Fail Co"})

        # Both companies: BCV provider
        for comp in (comp_a, comp_b):
            comp.currency_provider = "bcv"

        vef = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VEF")], limit=1,
        )

        call_log = []

        def fake_update_rates():
            call_log.append(self.env.company.id)
            if self.env.company.id == comp_a.id:
                raise RuntimeError("Simulated BCV failure")

        with patch.object(
            type(comp_a),
            "update_currency_rates",
            side_effect=fake_update_rates,
        ), patch.object(
            type(comp_a),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            currency_res_company.fields.Date,
            "today",
            return_value=date(2026, 7, 15),
        ):
            # Should NOT raise — failure is isolated via savepoint
            self.company.run_update_bcv_currency()

        # Both companies should have been attempted
        self.assertEqual(len(call_log), 2)

    def test_run_update_bcv_currency_schedules_retry_when_rate_missing(self):
        """A company left without a rate reprograms the BCV cron via ir.cron.trigger."""
        comp_a = self.company
        comp_a.currency_provider = "bcv"
        retry_at = currency_res_company.datetime(2026, 7, 15, 5, 30, 0)

        with patch.object(
            type(comp_a),
            "update_currency_rates",
            side_effect=RuntimeError("Simulated BCV failure"),
        ), patch.object(
            type(comp_a),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            currency_res_company.fields.Date,
            "today",
            return_value=date(2026, 7, 15),
        ), patch.object(
            type(comp_a),
            "_get_next_bcv_retry_time",
            return_value=retry_at,
        ) as mock_get_retry, patch.object(
            type(comp_a),
            "_schedule_bcv_retry",
            return_value=True,
        ) as mock_schedule:
            comp_a.run_update_bcv_currency()

        mock_get_retry.assert_called_once()
        mock_schedule.assert_called_once_with(retry_at)

    def test_run_update_bcv_currency_does_not_schedule_retry_when_rate_updated(self):
        """No retry is scheduled once every BCV company has today's rate."""
        comp_a = self.company
        comp_a.currency_provider = "bcv"
        vef = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VEF")], limit=1,
        )

        def fake_update_rates():
            self.env["res.currency.rate"].create(
                {
                    "currency_id": vef.id,
                    "company_id": self.env.company.id,
                    "name": date(2026, 7, 15),
                    "company_rate": 100.0,
                }
            )

        with patch.object(
            type(comp_a),
            "update_currency_rates",
            side_effect=fake_update_rates,
        ), patch.object(
            type(comp_a),
            "_is_bcv_update_window",
            return_value=True,
        ), patch.object(
            currency_res_company.fields.Date,
            "today",
            return_value=date(2026, 7, 15),
        ), patch.object(
            type(comp_a),
            "_schedule_bcv_retry",
        ) as mock_schedule:
            comp_a.run_update_bcv_currency()

        mock_schedule.assert_not_called()

    # ==================================================================
    # Mutation-style: _get_bcv_currency_rates rejection guards
    # ==================================================================

    def test_get_bcv_currency_rates_rejects_zero_rate(self):
        """EUR rate of zero is omitted from results."""
        html = self._bcv_multi_html({"EUR": ("euro", " 0,00")})
        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ):
            result = self.company._get_bcv_currency_rates(["EUR", "USD"])

        self.assertNotIn("EUR", result)
        self.assertIn("USD", result)

    def test_get_bcv_currency_rates_rejects_negative_rate(self):
        """EUR rate of -1 is omitted from results (already covered, reinforcement)."""
        html = self._bcv_multi_html({"EUR": ("euro", " -100,00")})
        with patch.object(
            currency_res_company.requests,
            "get",
            return_value=MockResponse(text=html),
        ):
            result = self.company._get_bcv_currency_rates(["EUR", "USD"])

        self.assertNotIn("EUR", result)
        self.assertIn("USD", result)
