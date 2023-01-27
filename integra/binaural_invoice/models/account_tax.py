from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"


    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None):
        currency = self.env.company.currency_foreign_id
        res = super()._prepare_tax_totals(base_lines, currency, tax_lines)
        _logger.warning("base_lineeeeees: %s", base_lines)
        _logger.warning("currencyyyyyyyyy: %s", currency)
        _logger.warning("tax_lineeeeees: %s", tax_lines)
        # rate = 0.0
        for values in base_lines:
            rate = values['record'].move_id.tax
            _logger.warning("values: %s", values['record'].move_id.tax)
            res.update({'foreign_amount_total': res['amount_total'] * rate, })
        return res

