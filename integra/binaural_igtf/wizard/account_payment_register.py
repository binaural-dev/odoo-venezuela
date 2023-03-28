from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import frozendict
from collections import defaultdict


import logging

_logging = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    def default_is_igtf(self):
        return self.env.company.module_binaural_base_igtf or False

    def default_igtf_percentage(self):
        return self.env.company.igtf_percentage or 0.0

    is_igtf = fields.Boolean(string="IGTF", default=default_is_igtf, help="IGTF", store=True)
    amount_with_igtf = fields.Float(
        string="Amount with IGTF", compute="_compute_amount_with_igtf", store=True
    )
    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        default=default_igtf_percentage,
        help="IGTF Percentage",
        store=True,
    )
    igtf_amount = fields.Monetary(
        string="IGTF Amount", compute="_compute_igtf_amount", store=True, help="IGTF Amount"
    )

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        readonly=False,
        compute="_compute_is_igtf",
        store=True,
    )

    @api.depends("journal_id", "is_igtf")
    def _compute_is_igtf(self):
        for payment in self:
            if payment.journal_id.is_igtf == True and payment.is_igtf and payment.currency_id.name == "USD":
                payment.is_igtf_on_foreign_exchange = True

    @api.depends("amount", "is_igtf")
    def _compute_igtf_amount(self):
        for payment in self:
            payment.igtf_amount = 0.0
            if payment.is_igtf and payment.journal_id.is_igtf and payment.currency_id.name == "USD":
                payment.igtf_amount = payment.amount * (payment.igtf_percentage / 100)

   

    # def _create_account_move_line_igtf_credit(self, payments):
    #     """Create account move lines for IGTF.

    #     :return: The account move lines to create.
    #     """
    #     account = self.env.company.account_igtf_id.id

    #     return self.env["account.move.line"].create(
    #         {
    #             "move_id": payments.line_ids.move_id.id,
    #             "name": "IGTF",
    #             "debit": 0,
    #             "credit": 3,
    #             "amount_currency": -3,
    #             "account_id": account,
    #             "partner_id": self.partner_id.id,
    #             # 'currency_id': self.currency_id.id
    #         }
    #     )
    
    # def _create_account_move_line_igtf_debit(self, payments):

    #     account = self.env.company.account_igtf_id.id

    #     return self.env["account.move.line"].create(
    #         {
    #             "move_id": payments.line_ids.move_id.id,
    #             "name": "IGTF",
    #             "debit": 3,
    #             "credit": 0,
    #             "amount_currency": 3,
    #             "account_id": account,
    #             "partner_id": self.partner_id.id,
    #             # 'currency_id': self.currency_id.id
    #         }
    #     )
