from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # TDE FIXME: move to l10n_ve_currency_rate_live
    edit_rate = fields.Boolean(
        compute="_compute_edit_rate",
    )

    def _compute_edit_rate(self):
        for record in self:
            record.edit_rate = (
                record.env.company.currency_provider == "bcv"
                and record.env.user.has_group(
                    "l10n_ve_accountant.group_fiscal_config_support"
                )
            )

    def unlink(self):
        raise UserError(_("It is not possible to delete currency records."))
        return super(ResCurrency, self).unlink()
