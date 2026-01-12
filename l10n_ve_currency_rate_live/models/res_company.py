from odoo import api, fields, models, _
from ...tools import binaural_bcv_query
import logging

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
            rates_bcv = {}
            can_update_habil_days = company.can_update_habil_days
            current_date = fields.Date.context_today(self)
            day = current_date.isoweekday()
            is_habil_day = day <= 5
            invalid_update_in_habil_day = not is_habil_day and can_update_habil_days
            if invalid_update_in_habil_day:
                return {}
            rates_bcv = binaural_bcv_query.get_currency_rates_of_the_day_bcv(self)
            if isinstance(rates_bcv, tuple):
                return {}

            final_rates = {"VEF": (1.0, current_date)}
            for currency_code, rate_data in rates_bcv.items():
                rate, date = rate_data
                if str(date) == str(current_date) and rate:
                    final_rates[currency_code] = (1.0 / rate, date)
            return final_rates
