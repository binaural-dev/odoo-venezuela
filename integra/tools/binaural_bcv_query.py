from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from odoo import fields
import requests
import logging
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)


def get_usd_rate_of_the_day_bcv(self):
    """This function return the rate of the day by the BCV website

    Raises:
        UserError: Error to connect with BCV, please check your internet connection or try again later

    Returns:
        tuple (float: rate of the day, date: date of the rate)
    """

    disable_warnings(InsecureRequestWarning)
    URL = "https://www.bcv.org.ve/"
    current_date = fields.Date.context_today(self)

    try:
        html_content = requests.get(URL, verify=False, timeout=5)
        soup = BeautifulSoup(html_content.text, "html.parser")

        usd_container = soup.find(id="dolar")
        usd_value = (
            usd_container.text.replace("\n", "").replace("USD", "").replace(",", ".").strip()
        )
        return (float(usd_value), current_date)
    except Exception as e:
        _logger.error(e)
        return (1, False)
