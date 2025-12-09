from odoo import api, fields, models, _
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
import requests
import logging
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.model
    def _parse_bcv_data(self, availible_currencies):
        companies = self.env["res.company"].search([])
        for company in companies:
            can_update_habil_days = company.can_update_habil_days
            current_date = fields.Date.context_today(company)
            day = current_date.isoweekday()
            is_habil_day = day <= 5
            invalid_update_in_habil_day = not is_habil_day and can_update_habil_days
            if invalid_update_in_habil_day:
                return
            usd_rate_bcv = company.get_usd_rate_of_the_day_bcv()
            is_valid_update_date = str(usd_rate_bcv[1]) == str(current_date)
            if not is_valid_update_date:
                return
            return {"USD": (1, usd_rate_bcv[1]), "VEF": usd_rate_bcv}
    
    @api.model
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
            html_content = requests.get(URL, verify=False, timeout=30)
            soup = BeautifulSoup(html_content.text, "html.parser")

            usd_container = soup.find(id="dolar")
            usd_value = (
                usd_container.text.replace("\n", "")
                .replace("USD", "")
                .replace(",", ".")
                .strip()
            )
            return (float(usd_value), current_date)
        except Exception as e:
            _logger.error(e)
            return (1, False)
