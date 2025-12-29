from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)
from odoo.fields import Monetary
from odoo.tools import float_repr

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
<<<<<<< HEAD
            )
=======
            )

    def _convert(self, from_amount, to_currency, company=None, date=None, round=True):  
        
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"
        if from_amount:
            to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        else:
            return 0.0

        return to_amount


    def round(self, amount):
        
        self.ensure_one()
        amount_float = float(amount)

        try:
            amount_float = float(amount)
        except (ValueError, TypeError):
            return super(ResCurrency, self).round(amount)

        if abs(amount_float - round(amount_float, 6)) > 1e-9:
            return amount_float

        return super(ResCurrency, self).round(amount_float)
>>>>>>> bbbad54d4ccdf022b696a8b3d6b2f2e5491b881b
