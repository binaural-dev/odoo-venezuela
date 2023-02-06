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

    #     _logger.warning("Currency is USD")

    #     foreign_amount = defaultdict(list)
        
    #     foreign_amount.update({
    #         'tax_group_amount': 15,
    #         'tax_group_base_amount': 15,
    #         'formatted_tax_group_amount': formatLang(self.env, 15, currency_obj=currency),
    #         'formatted_tax_group_base_amount': formatLang(self.env, 15 , currency_obj=currency),
    #     })

    #     res.update({
    #         'foreign_amount': foreign_amount,
    #     })
            
        # return res
