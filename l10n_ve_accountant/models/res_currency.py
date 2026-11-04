from odoo import models, fields, api, _

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

    def is_venezuelan_bolivar(self):
        """True when this currency is the Venezuelan Bolívar, VEF or VES.

        Odoo keeps VEF (pre-2018 redenomination) and VES (current) as separate
        currency records, so callers that mean "the local Bolívar" must not
        hardcode either one alone or they'll misbehave for companies still on
        the other record.
        """
        return self.name in ("VEF", "VES")
