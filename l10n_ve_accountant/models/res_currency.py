from odoo import models, fields, api, _
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

    def _convert(self, from_amount, to_currency, company=None, date=None, round=False):  
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
        # apply conversion rate
        if from_amount:
            to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        else:
            return 0.0

        # apply rounding
        return to_currency.round(to_amount) if round else to_amount