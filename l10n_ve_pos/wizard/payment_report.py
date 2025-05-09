from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
import pytz

import logging

_logger = logging.getLogger(__name__)


class PosPaymentReport(models.TransientModel):
    _name = "pos.payment.report"
    _description = "Point of Sale Details Report"

    def _default_pos_start_date(self):
        return fields.Datetime.today()

    def _default_pos_end_date(self):
        return fields.Datetime.now()

    def _default_pos_categories(self):
        return self.env["product.category"].search([("parent_id", "=", False)])

    start_date = fields.Datetime(required=True, default=_default_pos_start_date)
    end_date = fields.Datetime(required=True, default=_default_pos_end_date)

    pos_config_ids = fields.Many2many(
        "pos.config", default=lambda s: s.env["pos.config"].search([])
    )
    category_ids = fields.Many2many(
        "product.category", string="Categories", default=_default_pos_categories
    )

    show_categories = fields.Selection(
        selection=[
            ("1_level", "1st Level"),
            ("2_level", "2nd Level"),
            ("both", "Both"),
        ],
        default="both",
    )

    type_report = fields.Selection(
        selection=[("general", "General"), ("by_cash_register", "By Cash Register")],
        default="by_cash_register",
    )

    def generate_report(self):

        data = {
            "date_start": self.start_date,
            "date_stop": self.end_date,
            "config_ids": self.pos_config_ids.ids,
            "category_ids": self.category_ids.ids,
            "show_categories": self.show_categories,
            "type_report": self.type_report,
        }

        return self.env.ref("l10n_ve_pos.action_payment_report_pos").report_action(
            [], data=data
        )
