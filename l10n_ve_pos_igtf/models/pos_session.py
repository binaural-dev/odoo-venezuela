from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosSession(models.Model):
    _inherit = "pos.session"

    def action_pos_session_open(self):
        if not self.company_id.customer_account_igtf_id:
            raise ValidationError(
                _(
                    "You have the IGTF configuration turned on, first configure the account and the percentage"
                )
            )

        return super().action_pos_session_open()
