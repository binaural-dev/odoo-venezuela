from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from collections import defaultdict
from odoo.tools import float_is_zero, float_compare
import logging
_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = "pos.session"

    def load_pos_data(self):
        res = super().load_pos_data()
        payment_methods = res.get("pos.payment.method", [])
        missing_apply_igtf = [pm.get("id") for pm in payment_methods if "apply_igtf" not in pm]

        if missing_apply_igtf:
            rows = self.env["pos.payment.method"].search_read(
                [("id", "in", missing_apply_igtf)], ["id", "apply_igtf"]
            )
            apply_by_id = {row["id"]: row.get("apply_igtf", False) for row in rows}
            for payment_method in payment_methods:
                payment_method["apply_igtf"] = apply_by_id.get(
                    payment_method.get("id"), False
                )

        return res

    def action_pos_session_open(self):
        if not self.company_id.customer_account_igtf_id:
            raise ValidationError(
                _(
                    "You have the IGTF configuration turned on, first configure the account and the percentage"
                )
            )

        return super().action_pos_session_open()
