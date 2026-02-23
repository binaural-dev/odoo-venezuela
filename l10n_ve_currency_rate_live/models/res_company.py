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
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            }
            html_content = requests.get(URL, headers=headers, verify=False, timeout=20)
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
    def _parse_bcv_data(self, availible_currencies):
        """ This method receives the response from the bcv provider and formats it.
        It also handles the validation to prevent updating rates on non-working days (weekends)
        if the companies grouped by this provider have the 'can_update_habil_days' setting enabled.

        :param availible_currencies: recordset of the currencies we want to get the rates of.
        :return: dictionary with the currency codes as keys and the rate and date as values.
                 Example: {"VEF": (1.0, '2023-01-01'), "USD": (0.025, '2023-01-01')}
                 Returns {} if it's a non-working day and all companies block updates.
                 Returns {} if there's a communication error with the provider.
        """
        companies = self if self else self.env.company
        current_date = fields.Date.context_today(self)
        day = current_date.isoweekday()
        is_habil_day = day <= 5
        
        if not is_habil_day and all(company.can_update_habil_days for company in companies):
            return {}
        
        rates_bcv = self._get_bcv_currency_rates()
        if isinstance(rates_bcv, tuple):
            return {}

        final_rates = {"VEF": (1.0, current_date)}
        for currency_code, rate_data in rates_bcv.items():
            rate, date = rate_data
            if str(date) == str(current_date) and rate:
                final_rates[currency_code] = (1.0 / rate, date)
        return final_rates
