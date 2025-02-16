from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _convert(self, from_amount, to_currency, company, date, round=True, custom_rate=0.0):
        """Returns the converted amount of ``from_amount``` from the currency
           ``self`` to the currency ``to_currency`` for the given ``date`` and
           company.

           :param company: The company from which we retrieve the convertion rate
           :param date: The nearest date from which we retriev the conversion rate.
           :param round: Round the result or not
        """
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"
        assert company, "convert amount from unknown company"
        assert date, "convert amount from unknown date"
        # apply conversion rate
        if self == to_currency:
            to_amount = from_amount
        elif from_amount:
            if custom_rate > 0:
                to_amount = from_amount * custom_rate 
            else:
                to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        else:
            return 0.0

        # apply rounding
        return to_currency.round(to_amount) if round else to_amount
    

