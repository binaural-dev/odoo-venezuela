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

    def test_parse_bcv_data_skips_weekend_when_habil_days_enabled(self):
        saturday = date(2026, 6, 20)
        self.company.can_update_habil_days = True

        with patch.object(
            currency_res_company.fields.Date, "context_today", return_value=saturday
        ), patch.object(
            type(self.company),
            "_get_bcv_rate",
        ) as mock_get_rate:
            result = self.company._parse_bcv_data(
                self.env["res.currency"].browse([]),
            )

        self.assertEqual(result, {"USD": (1.0, saturday)})
        mock_get_rate.assert_not_called()

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

        bc_html = self._bcv_multi_html()

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
        """T13: DolarAPI falla, BCV scraping exitoso con EUR+CNY."""
        current_date = date(2026, 7, 15)
        self.company.can_update_habil_days = True

        bc_html = self._bcv_multi_html()

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

    def test_compute_currency_provider_sets_bcv_for_venezuela(self):
        self.company.country_id = self.country_ve
        self.company._compute_currency_provider()
        self.assertEqual(self.company.currency_provider, "bcv")
