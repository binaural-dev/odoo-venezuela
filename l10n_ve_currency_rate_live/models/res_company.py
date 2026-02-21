from odoo import api, fields, models, _

import logging
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.model
    def _get_bcv_currency_rates(self):
        """This function return the rate of the day by the BCV website using the BeautifulSoup library.
        We iterate over the active currencies and get the rate of the day for each currency available in the BCV website (See the bcv_currencies dictionary).

        Returns:
            dict: {currency_code: (rate, date)}
            tuple: (1, False) if an error occurs
        """

        disable_warnings(InsecureRequestWarning)
        URL = "https://www.bcv.org.ve/"
        current_date = fields.Date.context_today(self)

        try:
            html_content = requests.get(URL, verify=False, timeout=5)
            soup = BeautifulSoup(html_content.text, "html.parser")
            bcv_currencies = {
                "EUR": "euro",
                "CNY": "yuan",
                "TRY": "lira",
                "RUB": "rublo",
                "USD": "dolar",
            }
            active_currencies = self.env["res.currency"].search(
                [
                    ("active", "=", True),
                    ("name", "in", list(bcv_currencies.keys())),
                ]
            )
            currencies = {}
            if not active_currencies:
                return currencies
            for currency in active_currencies:
                if currency.name in bcv_currencies:
                    currency_container = soup.find(id=bcv_currencies[currency.name])
                    if not currency_container:
                        continue
                    currency_value = (
                        currency_container.text.replace("\n", "")
                        .replace(currency.name, "")
                        .replace(",", ".")
                        .strip()
                    )
                    currencies[currency.name] = (float(currency_value), current_date)
            return currencies
        except Exception as e:
            _logger.error(e)
            return (1, False)

    @api.model
    def _parse_bcv_data(self, available_currencies):
        companies = self.env["res.company"].search([])
        for company in companies:
            can_update_habil_days = company.can_update_habil_days
            current_date = fields.Date.context_today(self)
            day = current_date.isoweekday()
            is_habil_day = day <= 5
            invalid_update_in_habil_day = not is_habil_day and can_update_habil_days
            if invalid_update_in_habil_day:
                return {}
            rates_bcv = self._get_bcv_currency_rates()
            if isinstance(rates_bcv, tuple):
                return {}

            final_rates = {"VEF": (1.0, current_date)}
            for currency_code, rate_data in rates_bcv.items():
                rate, date = rate_data
                if str(date) == str(current_date) and rate:
                    final_rates[currency_code] = (1.0 / rate, date)
            _logger.warning("BCV rates: %s", final_rates)
            return final_rates
