from odoo import fields, models, _
from odoo.exceptions import UserError

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    can_update_habil_days = fields.Boolean(
        related="company_id.can_update_habil_days", readonly=False
    )

    def update_currency_rates_manually(self):
        self.ensure_one()
        if self.can_update_habil_days:
            current_date = fields.Date.context_today(self)
            is_habil_day = current_date.isoweekday() <= 5
            if not is_habil_day:
                raise UserError(_("You can not update currency rates manually in a non-habil day."))

        return super().update_currency_rates_manually()