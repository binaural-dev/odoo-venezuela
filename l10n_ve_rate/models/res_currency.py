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
        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        if not from_amount:
            return 0.0

        if custom_rate > 0:
            if company.currency_id != self and company.currency_id == self.env.ref("base.USD"):
                to_amount = from_amount / custom_rate
            else:
                to_amount = from_amount * custom_rate
        else:
            to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)

        return to_currency.round(to_amount) if round else to_amount