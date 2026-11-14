from odoo import _, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    igtf_percentage = fields.Float(
        "IGTF percentage", related="company_id.igtf_percentage", readonly=False
    )

    def _check_before_creating_new_session(self):
        res = super()._check_before_creating_new_session()
        self._check_igtf_account()
        return res

    def _check_igtf_account(self):
        """Refuse to open a session of a register that applies IGTF when the
        company has no IGTF account of its customers: the IGTF of every sale
        would have nowhere to go. A register without IGTF, in a company that
        has the module installed, opens as always."""
        self.ensure_one()
        igtf_in_use = any(self.payment_method_ids.currency_setting_ids.mapped("apply_igtf"))
        if igtf_in_use and not self.company_id.customer_account_igtf_id:
            raise ValidationError(
                _(
                    "You have the IGTF configuration turned on, first configure the account and the percentage"
                )
            )
