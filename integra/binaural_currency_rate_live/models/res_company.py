from odoo import api, fields, models, _
from ...tools import binaural_bcv_query

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    can_update_habil_days = fields.Boolean(default=True)

    @api.model
    def _parse_bcv_data(self, availible_currencies):
        companies = self.env['res.company'].search([])
        for company in companies:
            can_update_habil_days = company.can_update_habil_days
            current_date = fields.Date.context_today(self)
            day = current_date.isoweekday()
            is_habil_day = day <= 5
            invalid_update_in_habil_day = not is_habil_day and can_update_habil_days
            if invalid_update_in_habil_day:
                return
            usd_rate_bcv = binaural_bcv_query.get_usd_rate_of_the_day_bcv(self)
            is_valid_update_date = str(usd_rate_bcv[1]) == str(current_date)
            if not is_valid_update_date:
                return
            return {"USD": (1, usd_rate_bcv[1]), "VEF": usd_rate_bcv}