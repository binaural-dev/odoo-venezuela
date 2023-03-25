from odoo import api, models, fields, _
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
            if payment.journal_id.is_igtf == True and payment.is_igtf:
                payment.is_igtf_on_foreign_exchange = True


    def _create_payments(self):
        _logging.warning("CREATE PAYMENTS")
        res = super()._create_payments()
       
        res.line_ids.create({
            'name': 'IGTF',
            'debit': 0,
            'credit': 3,
            'account_id': 4,
            'move_id': res.id,
        })
        for lines in res.line_ids:
            if lines.debit > 0:
                lines.debit = lines.debit + 3
            _logging.warning("PAYMEEENTSSSSSSSSSSSS: %s", lines.account_id.name)
        return res
    
    def action_create_payments(self):
        _logging.warning("ACTION CREATE PAYMENTS")
        res = super().action_create_payments()
        _logging.warning("RESSSSSSSSSS: %s", res)
        return res
