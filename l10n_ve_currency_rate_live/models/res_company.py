from odoo import api, fields, models, _
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
import requests
import logging
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

# Mapping of ISO currency codes to BCV website HTML element IDs.
# The BCV publishes exchange rates for these 5 currencies in VEF.
BCV_CURRENCIES = {
    "EUR": "euro",
    "CNY": "yuan",
    "TRY": "lira",
    "RUB": "rublo",
    "USD": "dolar",
}

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.model
    def _get_bcv_currency_rates(self, available_currencies):
        """Scrape BCV website for all requested currencies in a single request.

        Only processes currencies present in both ``available_currencies``
        and ``BCV_CURRENCIES``.  Each currency is extracted by its HTML ID
        (e.g. ``#euro``, ``#yuan``, ``#lira``, ``#rublo``, ``#dolar``).

        :param list available_currencies: ISO codes of currencies to fetch
        :return: ``{code: (rate_VEF, published_date)}`` or ``{}`` on error
        :rtype: dict
        """
        target = {
            code for code in available_currencies
            if code in BCV_CURRENCIES
        }
        if not target:
            return {}

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

                # Shared publication date — the BCV only publishes one date
                published_date = None
                date_node = soup.find(
                    "span", class_="date-display-single",
                )
                if date_node and date_node.get("content"):
                    published_date = self._parse_source_date(
                        date_node["content"],
                    )

                result = {}
                for code in target:
                    html_id = BCV_CURRENCIES[code]
                    container = soup.find(id=html_id)
                    if not container:
                        _logger.warning(
                            "BCV scraping did not find #%s on attempt %s/%s",
                            html_id, attempt, SOURCE_MAX_ATTEMPTS,
                        )
                        continue

                    raw = (
                        container.text.replace("\n", "")
                        .replace(code, "")
                        .replace(",", ".")
                        .strip()
                    )
                    try:
                        rate = float(raw)
                    except (ValueError, TypeError):
                        _logger.warning(
                            "BCV scraping could not parse %s value '%s'",
                            code, raw,
                        )
                        continue
                    if rate <= 0:
                        _logger.warning(
                            "BCV scraping rejected %s rate %s (<= 0)",
                            code, rate,
                        )
                        continue

                    if published_date:
                        result[code] = (rate, published_date)

                if result:
                    return result

                _logger.warning(
                    "BCV scraping returned no valid currency rates "
                    "on attempt %s/%s", attempt, SOURCE_MAX_ATTEMPTS,
                )
            except Exception as exc:
                _logger.warning(
                    "BCV multi-currency scraping failed on attempt %s/%s: %s",
                    attempt, SOURCE_MAX_ATTEMPTS, exc,
                )
        return {}

    @api.model
    def _normalize_currency_rate(self, result, currency_code, vef_rate, current_date):
        """Normalise a VEF-denominated rate into USD terms and add to result.

        The BCV publishes rates as VEF per unit of foreign currency.
        Because ``_parse_bcv_data()`` uses USD as its base (``USD = 1.0``),
        secondary currencies need to be expressed as a ratio against USD.

        :param dict result: result dict (mutated in-place)
        :param str currency_code: ISO code (e.g. ``"EUR"``)
        :param float vef_rate: rate in VEF per unit of ``currency_code``
        :param date current_date: rate date
        """
        usd_vef = result.get("VEF")
        if isinstance(usd_vef, tuple):
            usd_vef = usd_vef[0]
        if usd_vef and vef_rate:
            # Expression: (VEF per 1 USD) / (VEF per 1 FOREIGN)
            #           = FOREIGN per 1 USD  ← parsed data convention
            result[currency_code] = (usd_vef / vef_rate, current_date)

    @api.model
    def _get_last_system_rate_for_currency(self, currency_code, current_date):
        """Get the last stored ``company_rate`` for any currency (fallback).

        :param str currency_code: ISO code (e.g. ``"EUR"``, ``"USD"``)
        :param date current_date: reference date for fallback search
        :return: ``company_rate`` or ``None``
        """
        company = self[:1] or self.env.company
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", currency_code)], limit=1)
        )
        if not currency:
            return None

        rate_model = self.env["res.currency.rate"]
        last_rate = rate_model.search(
            [
                ("company_id", "=", company.id),
                ("currency_id", "=", currency.id),
                ("name", "<=", current_date),
            ],
            order="name desc, id desc",
            limit=1,
        )
        if not last_rate:
            last_rate = rate_model.search(
                [
                    ("company_id", "=", company.id),
                    ("currency_id", "=", currency.id),
                ],
                order="name desc, id desc",
                limit=1,
            )
        return last_rate.company_rate if last_rate else None

    @api.model
    def _get_bcv_currency_rates(self, available_currencies):
        """Scrape BCV website for all requested currencies in a single request.

        Only processes currencies present in both ``available_currencies``
        and ``BCV_CURRENCIES``.  Each currency is extracted by its HTML ID
        (e.g. ``#euro``, ``#yuan``, ``#lira``, ``#rublo``, ``#dolar``).

        :param list available_currencies: ISO codes of currencies to fetch
        :return: ``{code: (rate_VEF, published_date)}`` or ``{}`` on error
        :rtype: dict
        """
        target = {
            code for code in available_currencies
            if code in BCV_CURRENCIES
        }
        if not target:
            return {}

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

                # Shared publication date — the BCV only publishes one date
                published_date = None
                date_node = soup.find(
                    "span", class_="date-display-single",
                )
                if date_node and date_node.get("content"):
                    published_date = self._parse_source_date(
                        date_node["content"],
                    )

                result = {}
                for code in target:
                    html_id = BCV_CURRENCIES[code]
                    container = soup.find(id=html_id)
                    if not container:
                        _logger.warning(
                            "BCV scraping did not find #%s on attempt %s/%s",
                            html_id, attempt, SOURCE_MAX_ATTEMPTS,
                        )
                        continue

                    raw = (
                        container.text.replace("\n", "")
                        .replace(code, "")
                        .replace(",", ".")
                        .strip()
                    )
                    try:
                        rate = float(raw)
                    except (ValueError, TypeError):
                        _logger.warning(
                            "BCV scraping could not parse %s value '%s'",
                            code, raw,
                        )
                        continue
                    if rate <= 0:
                        _logger.warning(
                            "BCV scraping rejected %s rate %s (<= 0)",
                            code, rate,
                        )
                        continue

                    if published_date:
                        result[code] = (rate, published_date)

                if result:
                    return result

                _logger.warning(
                    "BCV scraping returned no valid currency rates "
                    "on attempt %s/%s", attempt, SOURCE_MAX_ATTEMPTS,
                )
            except Exception as exc:
                _logger.warning(
                    "BCV multi-currency scraping failed on attempt %s/%s: %s",
                    attempt, SOURCE_MAX_ATTEMPTS, exc,
                )
        return {}

    @api.model
    def _normalize_currency_rate(self, result, currency_code, vef_rate, current_date):
        """Normalise a VEF-denominated rate into USD terms and add to result.

        The BCV publishes rates as VEF per unit of foreign currency.
        Because ``_parse_bcv_data()`` uses USD as its base (``USD = 1.0``),
        secondary currencies need to be expressed as a ratio against USD.

        :param dict result: result dict (mutated in-place)
        :param str currency_code: ISO code (e.g. ``"EUR"``)
        :param float vef_rate: rate in VEF per unit of ``currency_code``
        :param date current_date: rate date
        """
        usd_vef = result.get("VEF")
        if isinstance(usd_vef, tuple):
            usd_vef = usd_vef[0]
        if usd_vef and vef_rate:
            # Expression: (VEF per 1 USD) / (VEF per 1 FOREIGN)
            #           = FOREIGN per 1 USD  ← parsed data convention
            result[currency_code] = (usd_vef / vef_rate, current_date)

    @api.model
    def _get_last_system_rate_for_currency(self, currency_code, current_date):
        """Get the last stored ``company_rate`` for any currency (fallback).

        :param str currency_code: ISO code (e.g. ``"EUR"``, ``"USD"``)
        :param date current_date: reference date for fallback search
        :return: ``company_rate`` or ``None``
        """
        company = self[:1] or self.env.company
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", currency_code)], limit=1)
        )
        if not currency:
            return None

        rate_model = self.env["res.currency.rate"]
        last_rate = rate_model.search(
            [
                ("company_id", "=", company.id),
                ("currency_id", "=", currency.id),
                ("name", "<=", current_date),
            ],
            order="name desc, id desc",
            limit=1,
        )
        if not last_rate:
            last_rate = rate_model.search(
                [
                    ("company_id", "=", company.id),
                    ("currency_id", "=", currency.id),
                ],
                order="name desc, id desc",
                limit=1,
            )
        return last_rate.company_rate if last_rate else None

    @api.model
    def _parse_bcv_data(self, available_currencies):
        """Parse BCV exchange rates for all active currencies.

        Keeps the existing two-tier strategy for USD:
          1. DolarAPI (primary)
          2. BCV website scraping (fallback)

        For any other active BCV currency (EUR, CNY, TRY, RUB) the BCV
        website is scraped in a single additional HTTP request.  All rates
        are normalised against ``USD = 1.0``.

        .. note::

           ``available_currencies`` is a ``res.currency`` **recordset**
           (passed by the enterprise ``update_currency_rates()`` method).
           All other ``_parse_*_data()`` providers in
           ``currency_rate_live`` convert it via ``.mapped('name')``
           before iterating — we do the same here.
        """
        current_date = fields.Date.to_date(fields.Date.context_today(self))
        result = {"USD": (1.0, current_date)}
        available_currency_names = available_currencies.mapped("name")
        target_currencies = {
            c for c in available_currency_names if c in BCV_CURRENCIES
        }

        if self[:1].can_update_habil_days and current_date.isoweekday() > 5:
            return result

        rate_value, published_date = self._get_bcv_rate(
            expected_date=current_date,
        )
        if not rate_value or not published_date:
            fallback_rate = self._get_last_system_rate(current_date)
            if fallback_rate is not None and not bool(
                self[:1].can_update_habil_days,
            ):
                result["VEF"] = (fallback_rate, current_date)
            return result

        if not self._is_valid_rate_date(current_date, published_date):
            fallback_rate = self._get_last_system_rate(current_date)
            if fallback_rate is not None and not bool(
                self[:1].can_update_habil_days,
            ):
                result["VEF"] = (fallback_rate, current_date)
            return result

        result["VEF"] = (rate_value, current_date)

        # Include any other active BCV currencies
        non_usd = [c for c in target_currencies if c != "USD"]
        if non_usd:
            bc_rates = self._get_bcv_currency_rates(non_usd)
            for code, (vef_rate, pub_date) in bc_rates.items():
                if self._is_valid_rate_date(current_date, pub_date):
                    self._normalize_currency_rate(
                        result, code, vef_rate, current_date,
                    )

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
            # We use the current company in the context
            current_date = fields.Date.context_today(self)
            
            # Check if today is a business day (Monday=1, Sunday=7)
            day = current_date.isoweekday()
            is_habil_day = day <= 5
            
            # Condition to skip update if it's a weekend and the company restricts it
            if not is_habil_day and self.can_update_habil_days:
                _logger.info("BCV Update: Skipping update because it is not a business day.")
                return result

            usd_rate_data = self.get_usd_rate_of_the_day_bcv()
            rate_value = usd_rate_data[0]
            rate_date = usd_rate_data[1]

            # Validate that we actually got a date and it matches today (or the expected date)
            if not rate_date or str(rate_date) != str(current_date):
                _logger.warning("BCV Update: The rate date found (%s) does not match today (%s).", rate_date, current_date)
                return result

            # result dictionary structure: { 'CURRENCY_CODE': (factor, date), ... }
            # Note: Odoo expects (1.0, date) for the base currency of the provider.
            result = {
                "USD": (1.0, rate_date),
                "VEF": (rate_value, rate_date) 
            }
        except Exception as e:
            _logger.error("BCV Update: Critical error parsing data: %s", e)
            
        return result
    
    @api.model
    def get_usd_rate_of_the_day_bcv(self):
        """
        Performs web scraping on the BCV website to retrieve the official USD exchange rate.
        
        :return: A tuple containing (float: rate value, date: date of the rate).
                 Returns (1.0, False) in case of connection or parsing errors.
        """
        disable_warnings(InsecureRequestWarning)
        URL = "https://www.bcv.org.ve/"
        current_date = fields.Date.context_today(self)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            # Using a 30-second timeout to prevent the process from hanging indefinitely
            response = requests.get(URL, verify=False, timeout=30, headers=headers)
            response.raise_for_status() # Ensure we got a 200 OK status
            
            soup = BeautifulSoup(response.text, "html.parser")

            # Extracting the USD value from the specific HTML ID used by BCV
            usd_container = soup.find(id="dolar")
            if not usd_container:
                _logger.error("BCV Update: No se encontró el contenedor 'dolar' en la web del BCV.")
                return (1.0, False)

            usd_value = (
                usd_container.text.replace("\n", "")
                .replace("USD", "")
                .replace(",", ".")
                .strip()
            )
            return (float(usd_value), current_date)
        except requests.exceptions.RequestException as e:
            _logger.error("BCV Update: Connection error to BCV website: %s", e)
            return (1.0, False)
        except Exception as e:
            _logger.error("BCV Update: Unexpected error during scraping: %s", e)
            return (1.0, False)

    @api.depends('country_id')
    def _compute_currency_provider(self):
        super(ResCompany, self)._compute_currency_provider()
        
        for record in self:
            if record.country_id and record.country_id.code == 'VE':
                record.currency_provider = 'bcv'