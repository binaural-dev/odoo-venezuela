from odoo import api, fields, models, _
from collections import defaultdict
from odoo.tools.misc import formatLang
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None):
        currency = self.env.company.currency_foreign_id
        res = super()._prepare_tax_totals(base_lines, currency, tax_lines)
        if currency.id == 3:
            _logger.warning("Currency is USD")
            for values in base_lines:
                _logger.warning("values %s", values['taxes'].amount)
                rate = values['record'].move_id.tax
                res.update({'foreign_amount_total': res['amount_total'] * rate})
                res.update({'foreign_amount_untaxed': res['amount_untaxed'] * rate})
                
                group_by_subtotal = res['groups_by_subtotal'].copy()

                res.update({ 'foreign_groups_by_subtotal': group_by_subtotal })
                for totals in res['foreign_groups_by_subtotal'].values():
                    if totals[0]['tax_group_id'] == values['taxes'].tax_group_id.id:
                        totals[0]['tax_group_base_amount'] = values['record'].foreign_subtotal
                        totals[0]['tax_group_amount'] = 11111

                   
        _logger.warning("res %s", res)
        return res

