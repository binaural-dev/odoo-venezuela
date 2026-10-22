from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # Restringir la eliminación de monedas y la gestión de sus tasas de
    # cambio a quienes pertenezcan a group_fiscal_config_support.
    edit_rate = fields.Boolean(
        compute="_compute_edit_rate",
    )

    def _compute_edit_rate(self):
        for record in self:
            record.edit_rate = record.env.user.has_group(
                "l10n_ve_accountant.group_fiscal_config_support"
            )

    def unlink(self):
        if not self.env.user.has_group(
            "l10n_ve_accountant.group_fiscal_config_support"
        ):
            raise UserError(_("It is not possible to delete currency records."))
        return super().unlink()
