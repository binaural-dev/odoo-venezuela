from odoo import api, fields, models, _
from odoo.tools.misc import formatLang
from collections import defaultdict

import logging
import copy

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    # @api.model
    # def _prepare_tax_totals(self, base_lines, currency, tax_lines=None):
    #     currency = self.env.company.currency_foreign_id
    #     res = super()._prepare_tax_totals(base_lines, currency, tax_lines)
    #     _logger.warning("base_lines %s", base_lines)
    #     rate = 25

    #     if currency.id == 3:
    #         _logger.warning("Currency is USD")
            
    #         foreign_amount_total = copy.deepcopy(res['amount_total'])
    #         foreign_amount_untaxed = copy.deepcopy(res['amount_untaxed'])

    #         res.update({'foreign_amount_total': foreign_amount_total * rate})
    #         res.update({'foreign_amount_untaxed': foreign_amount_untaxed * rate})

    #         foreign_group_by_subtotal = copy.deepcopy(res['groups_by_subtotal'])

    #         res.update({ 'foreign_groups_by_subtotal': foreign_group_by_subtotal })

    #         totals = res['foreign_groups_by_subtotal'].values()
    #         for amount in totals:
    #             _logger.warning("amount", amount[0]['tax_group_base_amount'])
    #             for values in amount:
    #                 _logger.warning("values", values['tax_group_base_amount'])
    #                 values['tax_group_base_amount'] = base_lines[0]['record'].foreign_subtotal
    #                 values['tax_group_amount'] = base_lines[0]['record'].foreign_subtotal * base_lines[0]['taxes'].amount / 100
    #                 values['formatted_tax_group_amount'] = formatLang(self.env, values['tax_group_base_amount'] * base_lines[0]['taxes'].amount / 100, currency_obj=currency)
    #                 values['formatted_tax_group_base_amount'] = formatLang(self.env, base_lines[0]['record'].foreign_subtotal, currency_obj=currency)

    #             amount[0]['tax_group_base_amount'] += base_lines[0]['record'].foreign_subtotal
    #             amount[0]['tax_group_amount'] += amount[0]['tax_group_base_amount'] * base_lines[0]['taxes'].amount / 100
    #     return res
