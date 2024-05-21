from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta

import logging

_logger = logging.getLogger(__name__)


class PosPaymentReport(models.TransientModel):
    _name = "pos.payment.report"
    _description = "Point of Sale Details Report"

    def _default_pos_start_date(self):
        return fields.Datetime.now() + timedelta(days=-1)

    def _default_pos_end_date(self):
        return fields.Datetime.now() + timedelta(days=1)

    def _default_pos_categories(self):
        return self.env["pos.category"].search([])

    start_date = fields.Datetime(required=True, default=_default_pos_start_date)
    end_date = fields.Datetime(required=True, default=_default_pos_end_date)

    pos_config_ids = fields.Many2many(
        "pos.config", default=lambda s: s.env["pos.config"].search([])
    )
    category_ids = fields.Many2many(
        "pos.category", string="Categories", default=_default_pos_categories
    )

    def generate_report(self):
        data = {
            "date_start": self.start_date,
            "date_stop": self.end_date,
            "config_ids": self.pos_config_ids.ids,
            "category_ids": self.category_ids.ids,
        }
        return self.env.ref("binaural_pos.action_payment_report_pos").report_action([], data=data)
