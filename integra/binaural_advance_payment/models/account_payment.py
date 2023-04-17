from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_advance_payment = fields.Boolean(
        default=False,
        help="Check this box if this payment is an advance payment",
    )

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        for rec in self:
            if rec.is_advance_payment:
                if rec.partner_type == "customer" and rec.payment_type == "inbound":
                    line = rec.line_ids.filtered(
                        lambda l: l.account_id.account_type == "asset_receivable"
                    )
                    if line:
                        _logger.warning("partner_typeeeeeeeeeeeeeee: %s", rec.partner_type)
                        line.account_id = self.env.company.advance_customer_account_id.id
                if rec.partner_type == "supplier" and rec.payment_type == "outbound":
                    line = rec.line_ids.filtered(
                        lambda l: l.account_id.account_type == "liability_payable"
                    )
                    if line:
                        _logger.warning("partner_typeeeeeeeeeeeeeeee: %s", rec.partner_type)
                        line.account_id = self.env.company.advance_supplier_account_id.id

        return res

    # @api.depends("journal_id", "partner_id", "partner_type", "is_internal_transfer", "is_advance_payment")
    # def _compute_destination_account_id(self):

    #     res = super(AccountPayment, self)._compute_destination_account_id()
    #     for rec in self:
    #         if rec.is_advance_payment:
    #             customer_account = self.env.company.advance_customer_account_id.id
    #             supplier_account = self.env.company.advance_supplier_account_id.id
    #             if not customer_account or not supplier_account:
    #                 raise UserError(
    #                     _(
    #                         "You must configure the advance customer account and the advance supplier account in the company settings"
    #                     )
    #                 )
    #             if rec.partner_type == "customer":
    #                 rec.destination_account_id = customer_account
    #             elif rec.partner_type == "supplier":
    #                 rec.destination_account_id = supplier_account
    #         else:
    #             return res

    # for rec in self:
    #     if rec.is_advance_payment:
    #         customer_account = self.env.company.advance_customer_account_id.id
    #         supplier_account = self.env.company.advance_supplier_account_id.id
    #         if not customer_account or not supplier_account:
    #             raise UserError(
    #                 _(
    #                     "You must configure the advance customer account and the advance supplier account in the company settings"
    #                 )
    #             )
    #         if rec.partner_type == "customer":
    #             rec.destination_account_id = customer_account
    #         elif rec.partner_type == "supplier":
    #             rec.destination_account_id = supplier_account
    #     else:
    #         super(AccountPayment, rec)._compute_destination_account_id()
    # return
