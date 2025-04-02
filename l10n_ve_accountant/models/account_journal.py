from odoo.exceptions import UserError
from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            self._validate_support_user_group(vals)

        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            if "type" in vals:
                record._validate_support_user_group(vals)
        return super().write(vals)

    def _validate_support_user_group(self, vals):
        user = self.env.user
        is_support_user = user.has_group("l10n_ve_accountant.group_fiscal_config_support")

        if not is_support_user:
            if vals["type"] not in ["bank", "general", "cash"]:

                raise UserError(
                    _(
                        f"You do not have permissions to create/update a journal with this type."
                    )
                )

        return
