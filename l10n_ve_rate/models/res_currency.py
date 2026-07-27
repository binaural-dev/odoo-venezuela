from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _convert(self, from_amount, to_currency, company=None, date=None, round=True, custom_rate=0.0):
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"
        assert company, "convert amount from unknown company"
        assert date, "convert amount from unknown date"

        if from_amount:
            if custom_rate > 0:
               
                if company.currency_id == self.env.ref("base.USD") and to_currency != self:
                    to_amount = from_amount / custom_rate
                else:
                    to_amount = from_amount * custom_rate
               
            else:
                to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        else:
            return 0.0

        return to_currency.round(to_amount) 