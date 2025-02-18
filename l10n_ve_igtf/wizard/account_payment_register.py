from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    is_igtf = fields.Boolean(
        string="IGTF", compute="_compute_check_igtf", help="IGTF", store=True
    )
    amount_with_igtf = fields.Float(
        string="Amount with IGTF", compute="_compute_amount_with_igtf", store=True
    )
    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        compute="_compute_igtf_percentage",
        help="IGTF Percentage",
        store=True,
    )
    igtf_amount = fields.Float(
        string="IGTF Amount",
        compute="_compute_igtf_amount",
        store=True,
        help="IGTF Amount",
    )

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        readonly=False,
        store=True,
    )

    amount_without_difference = fields.Float(
        string="Amount without Difference",
        compute="_compute_amount_without_difference",
        store=True,
    )
    igtf_percentage_text = fields.Char(
        string="IGTF Percentage text",
        compute="_compute_igtf_percentage_text",
        help="IGTF Percentage Text",
        store=True,
    )

    @api.depends("journal_id", "currency_id")
    def _compute_check_igtf(self):
        for payment in self:
            payment.is_igtf = False
            if (
                payment.currency_id.id == self.env.ref("base.USD").id
                and payment.journal_id.currency_id.id == self.env.ref("base.USD").id
            ):
                for line in payment.line_ids:
                    if (
                        self.env.company.taxpayer_type == "ordinary"
                        and line.move_id.move_type == "out_invoice"
                    ):
                        payment.is_igtf = False
                    if (
                        self.env.company.taxpayer_type == "ordinary"
                        and line.move_id.partner_id.taxpayer_type == "ordinary"
                        and line.move_id.move_type == "in_invoice"
                    ):
                        payment.is_igtf = False

                    payment.is_igtf = True

    @api.depends("is_igtf")
    def _compute_igtf_percentage(self):
        for payment in self:
            payment.igtf_percentage = payment.env.company.igtf_percentage
            if (
                payment.env.company.taxpayer_type == "special"
                and payment.partner_id.taxpayer_type != "special"
                and payment.partner_type == "supplier"
            ):
                payment.igtf_percentage = 2.0

    @api.depends("igtf_percentage")
    def _compute_igtf_percentage_text(self):
        for record in self:
            record.igtf_percentage_text = f"IGTF({record.igtf_percentage:.2f})%"

    @api.depends("amount", "payment_difference")
    def _compute_amount_without_difference(self):
        for payment in self:
            payment.amount_without_difference = payment.amount
            if payment.payment_difference < 0:
                payment.amount_without_difference = (
                    payment.amount + payment.payment_difference
                )

    @api.depends("amount", "is_igtf", "igtf_amount")
    def _compute_amount_with_igtf(self):
        for payment in self:
            payment.amount_with_igtf = payment.amount + payment.igtf_amount

    @api.onchange("journal_id", "is_igtf", "currency_id")
    def _compute_is_igtf(self):
        for payment in self:
            if (
                payment.journal_id.is_igtf
                and payment.currency_id.id == self.env.ref("base.USD").id
            ):
                payment.is_igtf_on_foreign_exchange = True

            else:
                payment.is_igtf_on_foreign_exchange = False

    @api.depends("amount", "is_igtf", "is_igtf_on_foreign_exchange")
    def _compute_igtf_amount(self):
        for payment in self:
            payment.igtf_amount = 0.0
            if (
                payment.journal_id.is_igtf
                and payment.currency_id.id == self.env.ref("base.USD").id
                and payment.is_igtf_on_foreign_exchange
            ):
                payment_amount = payment.amount
                if payment.payment_difference < 0:
                    payment_amount = payment.amount + payment.payment_difference
                payment.igtf_amount = payment_amount * (payment.igtf_percentage / 100)

    def _init_payments(self, to_process, edit_mode=False):
        """Create the payments from the wizard's values.
        IGTF fields are added to the payment values to be created.

        :param to_process: A list of dicts containing the values to create the payments.

        :return: A list of ids of the created payments.
        """
        to_process[0]["create_vals"]["igtf_amount"] = self.igtf_amount
        to_process[0]["create_vals"]["igtf_percentage"] = self.igtf_percentage
        to_process[0]["create_vals"][
            "is_igtf_on_foreign_exchange"
        ] = self.is_igtf_on_foreign_exchange

        res = super(AccountPaymentRegisterIgtf, self)._init_payments(
            to_process, edit_mode
        )
        return res

    def _create_payments(self):
        """Create payment and add bi_igtf to the invoice.
        the bi_igtf is the amount of the payment minus the igtf amount.
        this field is used to calculate the igtf amount on the invoice on the tax widget.

        Returns:
            Payment: The created payment.
        """
        res = super(AccountPaymentRegisterIgtf, self)._create_payments()
        for payment in res:
            if (
                payment.journal_id.is_igtf == True
                and payment.currency_id.id == self.env.ref("base.USD").id
                and payment.is_igtf_on_foreign_exchange
            ):
                if self.igtf_percentage != 3:
                    if payment.reconciled_invoice_ids:
                        payment.reconciled_invoice_ids.is_two_percentage = True

                    if payment.reconciled_bill_ids:
                        payment.reconciled_bill_ids.is_two_percentage = True

                if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                    if payment.reconciled_invoice_ids:
                        payment.reconciled_invoice_ids.bi_igtf += (
                            self.amount_without_difference * self.foreign_rate
                        )

                    if payment.reconciled_bill_ids:
                        payment.reconciled_bill_ids.bi_igtf += (
                            self.amount_without_difference * self.foreign_rate
                        )
                else:
                    if payment.reconciled_invoice_ids:
                        payment.reconciled_invoice_ids.bi_igtf += (
                            self.amount_without_difference
                        )

                    if payment.reconciled_bill_ids:
                        payment.reconciled_bill_ids.bi_igtf += (
                            self.amount_without_difference
                        )
        return res
