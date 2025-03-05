from odoo import models, fields, api
from odoo.exceptions import ValidationError
import pytz
from datetime import datetime


class PosDetails(models.TransientModel):
    _inherit = "pos.details.wizard"

    def generate_report(self):
        user_tz = self.env.user.tz or "UTC"
        start_date_user_tz = self.start_date.astimezone(pytz.timezone(user_tz))
        end_date_user_tz = self.end_date.astimezone(pytz.timezone(user_tz))

        data = {
            "start_date_user_tz": start_date_user_tz,
            "end_date_user_tz": end_date_user_tz,
            "date_start": self.start_date,
            "date_stop": self.end_date,
            "config_ids": self.pos_config_ids.ids,
        }
        return self.env.ref("point_of_sale.sale_details_report").report_action(
            [], data=data
        )