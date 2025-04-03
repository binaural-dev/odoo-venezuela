from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from collections import defaultdict
from odoo.tools import float_is_zero, float_compare


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("apply_igtf")
        return res

    def action_pos_session_open(self):
        if not self.company_id.customer_account_igtf_id:
            raise ValidationError(_("First configure the account and the percentage"))

        return super().action_pos_session_open()
