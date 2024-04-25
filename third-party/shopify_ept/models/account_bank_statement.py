# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountBankStatement(models.Model):
    """
    This model is inherited for adding reference of Payout report into Bank statement.
    @author: Maulik Barad on Date 02-Dec-2020.
    """
    _inherit = 'account.bank.statement'

    shopify_payout_ref = fields.Char(string='Shopify Payout Reference')
