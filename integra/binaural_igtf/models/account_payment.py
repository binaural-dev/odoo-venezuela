from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"

    def default_is_igtf(self):
        return self.env.company.module_binaural_base_igtf or False

    def default_igtf_percentage(self):
        return self.env.company.igtf_percentage or 0.0

    is_igtf = fields.Boolean(string="IGTF", default=default_is_igtf, help="IGTF", store=True)

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        readonly=False,
        compute="_compute_is_igtf",
        store=True,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        default=default_igtf_percentage,
        help="IGTF Percentage",
        store=True,
    )

    igtf_amount = fields.Monetary(
        string="IGTF Amount",
        compute="_compute_igtf_amount",
        store=True,
        help="IGTF Amount",
    )

    @api.depends("journal_id", "is_igtf")
    def _compute_is_igtf(self):
        for payment in self:
            if payment.journal_id.is_igtf == True and payment.is_igtf:
                payment.is_igtf_on_foreign_exchange = True

    @api.depends("amount", "is_igtf")
    def _compute_igtf_amount(self):
        for payment in self:
            payment.igtf_amount = 0.0
            if payment.is_igtf and payment.journal_id.is_igtf:
                payment.igtf_amount = payment.amount * (payment.igtf_percentage / 100)

    
    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(write_off_line_vals)

        credit_line = [line for line in vals]

        credit_line[1]['credit'] = credit_line[1]['credit'] - 3.0


        vals[1].update({"amount_currency": -97,
                        "credit": 91})

        vals.append({"name": "IGTF",
                "debit": 0,
                "credit": 3,
                "amount_currency": -3,
                "account_id": 8,
                "partner_id": self.partner_id.id,})
  
        return vals