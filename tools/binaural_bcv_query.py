from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from odoo import fields
import requests
import logging
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)


def get_currency_rates_of_the_day_bcv(self):
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
