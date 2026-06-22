from odoo import api, fields, models
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
import requests
from bs4 import BeautifulSoup

BCV_URL = "https://www.bcv.org.ve/"
BCV_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
VEF_CURRENCY_CODE = "VEF"


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.model
    def _parse_bcv_data(self, available_currencies):
        current_date = fields.Date.context_today(self)
        result = {"USD": (1.0, current_date)}

        if self[:1].can_update_habil_days and current_date.isoweekday() > 5:
            return result

        rate_value, published_date = self._scrape_bcv_rate()
        if not rate_value or not published_date:
            return result

        if published_date > current_date:
            return result

        # After midnight we keep the latest published BCV rate, but store it
        # with the new Odoo date so customers on late shifts are not affected earlier.
        result["VEF"] = (rate_value, current_date)
        return result

    @api.model
    def _scrape_bcv_rate(self):
        disable_warnings(InsecureRequestWarning)
        try:
            response = requests.get(
                BCV_URL,
                verify=False,
                timeout=30,
                headers=BCV_HEADERS,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            usd_container = soup.find(id="dolar")
            if not usd_container:
                return (None, None)

            usd_value = (
                usd_container.text.replace("\n", "")
                .replace("USD", "")
                .replace(",", ".")
                .strip()
            )
            rate = float(usd_value)

            published_date = None
            date_node = soup.find("span", class_="date-display-single")
            if date_node and date_node.get("content"):
                published_date = fields.Date.from_string(date_node["content"][:10])
            return (rate, published_date)
        except Exception:
            return (None, None)

    @api.model
    def get_usd_rate_of_the_day_bcv(self):
        rate, date = self._scrape_bcv_rate()
        return (rate if rate is not None else 1, date or False)

    @api.model
    def run_update_bcv_currency(self):
        today = fields.Date.today()
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
