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
    igtf_amount = fields.Float(
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

    @api.depends("amount", "is_igtf", "igtf_amount")
    def _compute_amount_with_igtf(self):
        for payment in self:
            payment.amount_with_igtf = payment.amount + payment.igtf_amount
            _logging.warning("payment.amount_with_igtf: %s", payment.amount_with_igtf)

    @api.depends("journal_id", "is_igtf", "currency_id")
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
                _logging.warning("payment.igtf_amount: %s", payment.igtf_amount)

                

    def _init_payments(self, to_process, edit_mode=False):
        """ Create the payments from the wizard's values.
        IGTF fields are added to the payment values to be created. 
        
        :param to_process: A list of dicts containing the values to create the payments.

        :return: A list of ids of the created payments.
        """
        to_process[0]['create_vals']['amount'] = to_process[0]['create_vals']['amount'] + self.igtf_amount
        to_process[0]['create_vals']['igtf_amount'] = self.igtf_amount
        to_process[0]['create_vals']['igtf_percentage'] = self.igtf_percentage
        
        res = super(AccountPaymentRegisterIgtf, self)._init_payments(to_process, edit_mode)
        return res
    
    def _create_payments(self):
        """ Create payment and add bi_igtf to the invoice.
        the bi_igtf is the amount of the payment minus the igtf amount.
        this field is used to calculate the igtf amount on the invoice on the tax widget.

        Returns:
            Payment: The created payment.
        """
        res = super(AccountPaymentRegisterIgtf, self)._create_payments()
        for payment in res:
            if payment.journal_id.is_igtf == True and payment.is_igtf and payment.currency_id.name == "USD":
                if payment.reconciled_invoice_ids:
                    payment.reconciled_invoice_ids.write({'bi_igtf': payment.amount - payment.igtf_amount})
                if payment.reconciled_bill_ids:
                    payment.reconciled_bill_ids.write({'bi_igtf': payment.amount - payment.igtf_amount})
        return res
