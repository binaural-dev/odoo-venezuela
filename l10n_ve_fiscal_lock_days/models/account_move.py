from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    def get_last_day_previous_fortnight(self, period):
        today = date.today()
        if period == "biweekly":
            if today.day > 15:
                return today.replace(day=15)
            else:
                last_month = today.replace(day=1) - timedelta(days=1)
                return last_month
        else:
            last_month = today.replace(day=1) - timedelta(days=1)
            return last_month

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for vals in res:
            if (
                vals.company_id.lock_date_tax_validation
                and vals.company_id.tax_period
                and vals.move_type in ["out_invoice", "out_refund"]
            ):
                last_day = self.get_last_day_previous_fortnight(
                    vals.company_id.tax_period
                )
                if vals.company_id.tax_lock_date != last_day:
                    raise UserError(
                        "Debe bloquear la quincena o mes anterior antes de crear nuevas facturas en un periodo fiscal nuevo"
                    )
        return res
