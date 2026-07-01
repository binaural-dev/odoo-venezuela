import logging
from datetime import datetime

from odoo import api, fields, models
import pytz
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
import requests
from bs4 import BeautifulSoup

BCV_URL = "https://www.bcv.org.ve/"
DOLAR_API_STATUS_URL = "https://ve.dolarapi.com/v1/estado"
DOLAR_API_OFFICIAL_URL = "https://ve.dolarapi.com/v1/dolares/oficial"
BCV_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
API_TIMEOUT = 15
SOURCE_MAX_ATTEMPTS = 3
BCV_TIMEZONE = "America/Caracas"
BCV_WINDOW_START_HOUR = 4
BCV_WINDOW_END_HOUR = 6
VEF_CURRENCY_CODE = "VEF"

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.depends("country_id")
    def _compute_currency_provider(self):
        result = super()._compute_currency_provider()
        for record in self:
            if record.country_id and record.country_id.code == "VE":
                record.currency_provider = "bcv"
        return result

    @api.model
    def _parse_bcv_data(self, available_currencies):
        current_date = fields.Date.to_date(fields.Date.context_today(self))
        result = {"USD": (1.0, current_date)}
        fallback_rate = None

        if self[:1].can_update_habil_days and current_date.isoweekday() > 5:
            return result

        rate_value, published_date = self._get_bcv_rate(expected_date=current_date)
        if not rate_value or not published_date:
            fallback_rate = self._get_last_system_rate(current_date)
            if fallback_rate is not None and not bool(self[:1].can_update_habil_days):
                result["VEF"] = (fallback_rate, current_date)
            return result

        if not self._is_valid_rate_date(current_date, published_date):
            fallback_rate = self._get_last_system_rate(current_date)
            if fallback_rate is not None and not bool(self[:1].can_update_habil_days):
                result["VEF"] = (fallback_rate, current_date)
            return result

        result["VEF"] = (rate_value, current_date)
        return result

    @api.model
    def _is_bcv_update_window(self, now_local):
        if BCV_WINDOW_START_HOUR <= now_local.hour < BCV_WINDOW_END_HOUR:
            return True
        return now_local.hour == BCV_WINDOW_END_HOUR and now_local.minute == 0

    @api.model
    def _is_valid_rate_date(self, current_date, published_date):
        if not published_date:
            return False
        if published_date == current_date:
            return True

        # When enabled, accept the next published business-day rate.
        if published_date > current_date:
            return bool(self[:1].can_update_habil_days)

        # When disabled, keep using the last available published rate.
        return not bool(self[:1].can_update_habil_days)

    @api.model
    def _get_last_system_rate(self, current_date):
        company = self[:1] or self.env.company
        vef = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", VEF_CURRENCY_CODE)], limit=1,
        )
        if not vef:
            return None

        rate_model = self.env["res.currency.rate"]
        last_rate = rate_model.search(
            [
                ("company_id", "=", company.id),
                ("currency_id", "=", vef.id),
                ("name", "<=", current_date),
            ],
            order="name desc, id desc",
            limit=1,
        )
        if not last_rate:
            last_rate = rate_model.search(
                [
                    ("company_id", "=", company.id),
                    ("currency_id", "=", vef.id),
                ],
                order="name desc, id desc",
                limit=1,
            )
        return last_rate.company_rate if last_rate else None

    @api.model
    def _parse_source_date(self, value):
        if not value:
            return None
        try:
            return fields.Date.to_date(value[:10])
        except Exception:
            _logger.warning("BCV source returned an invalid date: %s", value)
            return None

    @api.model
    def _get_bcv_rate_from_api(self, expected_date=None):
        for attempt in range(1, SOURCE_MAX_ATTEMPTS + 1):
            try:
                status_response = requests.get(
                    DOLAR_API_STATUS_URL,
                    timeout=API_TIMEOUT,
                    headers=BCV_HEADERS,
                )
                status_response.raise_for_status()
                api_status = (status_response.json().get("estado") or "").strip().lower()
                if api_status != "disponible":
                    _logger.warning("DolarAPI healthcheck returned status '%s'", api_status)
                    return (None, None)

                official_response = requests.get(
                    DOLAR_API_OFFICIAL_URL,
                    timeout=API_TIMEOUT,
                    headers=BCV_HEADERS,
                )
                official_response.raise_for_status()
                payload = official_response.json()

                rate_value = payload.get("promedio")
                if rate_value is None:
                    rate_value = payload.get("venta") or payload.get("compra")
                published_date = self._parse_source_date(payload.get("fechaActualizacion"))
                if rate_value is None or not published_date:
                    return (None, None)
                if expected_date and published_date != expected_date:
                    _logger.warning(
                        "DolarAPI returned stale rate date %s while expecting %s",
                        published_date,
                        expected_date,
                    )
                    return (None, None)
                return (float(rate_value), published_date)
            except Exception as exc:
                _logger.warning(
                    "DolarAPI official rate fetch failed on attempt %s/%s: %s",
                    attempt,
                    SOURCE_MAX_ATTEMPTS,
                    exc,
                )
        return (None, None)

    @api.model
    def _scrape_bcv_rate(self):
        disable_warnings(InsecureRequestWarning)
        for attempt in range(1, SOURCE_MAX_ATTEMPTS + 1):
            try:
                response = requests.get(
                    BCV_URL,
                    verify=False,
                    timeout=30,
                    headers=BCV_HEADERS,
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                # Extracting the USD value from the specific HTML ID used by BCV
                usd_container = soup.find(id="dolar")
                if not usd_container:
                    _logger.warning("BCV scraping did not find #dolar on attempt %s/%s", attempt, SOURCE_MAX_ATTEMPTS)
                    continue

                usd_value = (
                    usd_container.text.replace("\n", "")
                    .replace("USD", "")
                    .replace(",", ".")
                    .strip()
                )
                rate = float(usd_value)

                published_date = None
                date_node = usd_container.find_next("span", class_="date-display-single")
                if date_node and date_node.get("content"):
                    published_date = self._parse_source_date(date_node["content"])
                if not published_date:
                    _logger.warning(
                        "BCV scraping did not find a valid published date on attempt %s/%s",
                        attempt,
                        SOURCE_MAX_ATTEMPTS,
                    )
                    continue
                return (rate, published_date)
            except Exception as exc:
                _logger.warning(
                    "BCV scraping failed on attempt %s/%s: %s",
                    attempt,
                    SOURCE_MAX_ATTEMPTS,
                    exc,
                )
        return (None, None)

    @api.model
    def _get_bcv_rate(self, expected_date=None):
        rate_value, published_date = self._get_bcv_rate_from_api(
            expected_date=expected_date,
        )
        if rate_value and published_date:
            return (rate_value, published_date)
        return self._scrape_bcv_rate()

    @api.model
    def get_usd_rate_of_the_day_bcv(self):
        rate, date = self._get_bcv_rate(
            expected_date=fields.Date.to_date(fields.Date.context_today(self)),
        )
        return (rate if rate is not None else 1, date or False)

    @api.model
    def run_update_bcv_currency(self):
        try:
            timezone = pytz.timezone(BCV_TIMEZONE)
        except Exception:
            timezone = pytz.UTC
        now_local = datetime.now(timezone)
        if not self._is_bcv_update_window(now_local):
            return

        today = fields.Date.to_date(fields.Date.today())
        Rate = self.env["res.currency.rate"]
        vef = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search(
                [("name", "=", VEF_CURRENCY_CODE)],
                limit=1,
            )
        )
        if not vef:
            return

        bcv_companies = self.search(
            [
                ("currency_provider", "=", "bcv"),
                # Child companies inherit the shared rate through their parent company.
                ("parent_id", "=", False),
            ]
        )
        for company in bcv_companies:
            already_today = Rate.search_count(
                [
                    ("company_id", "=", company.id),
                    ("currency_id", "=", vef.id),
                    ("name", "=", today),
                ]
            )
            if already_today:
                continue
            company.with_context(suppress_errors=True).update_currency_rates()
