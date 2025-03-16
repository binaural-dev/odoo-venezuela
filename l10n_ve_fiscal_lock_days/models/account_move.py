from odoo import fields, models, api, _
from odoo.exceptions import ValidationError 
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    def get_last_day_previous_fortnight(self, period):
        today = date.today()
        if period == "fortnightly":
            if today.day > 15:
                return today.replace(day=15)
            else:
                last_month = today.replace(day=1) - timedelta(days=1)
                return last_month
        if period == "monthly":
            last_month = today.replace(day=1) - timedelta(days=1)
            return last_month
        else:
            return False

    def _check_tax_lock_date(self):
        for move in self:
            if (
                move.company_id.lock_date_tax_validation
                and move.move_type in ["out_invoice", "out_refund"]
            ):
                last_day = self.get_last_day_previous_fortnight(
                    move.company_id.tax_period
                )
                if move.company_id.tax_lock_date != last_day:
                    raise ValidationError(
                        _("You must lock the previous fortnight or month before creating or posting invoices in a new fiscal period.")
                    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._check_tax_lock_date()
        return res

    def action_post(self):
        self._check_tax_lock_date()
        return super().action_post()


