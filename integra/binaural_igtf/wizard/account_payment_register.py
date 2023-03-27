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
        res = super()._create_payments()
        # res.action_draft()

        _logging.warning("REES: %s", res)


        res.line_ids += self._create_account_move_line_igtf(res)
        res.line_ids.move_id.button_draft()
        credit_line = res.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        _logging.warning("CREDIT LINE: %s", credit_line.account_id.name)
        credit_line.credit = credit_line.credit - 3.0
        credit_line.amount_currency = credit_line.amount_currency - 3.0

        for line in res.line_ids:
            if line.name == "IGTF":
                line.debit += 3.0
                line.amount_currency += -3.0

        res.line_ids.move_id.action_post()

        return res
    
    

    def _create_account_move_line_igtf(self, payments):
        """Create account move lines for IGTF.

        :return: The account move lines to create.
        """
        account = self.env.company.account_igtf_id.id

        return self.env["account.move.line"].create(
            {
                "move_id": payments.line_ids.move_id.id,
                "name": "IGTF",
                "debit": 0,
                "credit": 0,
                "amount_currency": 0,
                "account_id": account,
                "partner_id": self.partner_id.id,
                # 'currency_id': self.currency_id.id
            }
        )
