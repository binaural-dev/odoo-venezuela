from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
from odoo.tools.sql import column_exists, create_column
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        help="IGTF on Foreign Exchange?",
        readonly=False,
        compute="_compute_is_igtf",
        store=True,
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

    amount_with_igtf = fields.Float(
        string="Amount with IGTF", compute="_compute_amount_with_igtf", store=True
    )

    igtf_percentage_text = fields.Char(
        string="IGTF Percentage text",
        compute="_compute_igtf_percentage_text",
        help="IGTF Percentage Text",
        store=True,
    )

    @api.depends('partner_id', 'amount', 'is_igtf_on_foreign_exchange')
    def _compute_igtf_percentage(self):
        for payment in self:
            payment.igtf_percentage = payment.env.company.igtf_percentage
            if (
                payment.is_igtf_on_foreign_exchange
                and payment.env.company.taxpayer_type == "special"
                and payment.partner_id.taxpayer_type != "special"
                and payment.partner_type == "supplier"
            ):
                payment.igtf_percentage = 2.0

    @api.depends("igtf_percentage")
    def _compute_igtf_percentage_text(self):
        for record in self:
            record.igtf_percentage_text = f"IGTF({record.igtf_percentage:.2f})%"

    @api.depends("amount", "igtf_amount")
    def _compute_amount_with_igtf(self):
        for payment in self:
            if not payment.amount_with_igtf:
                payment.amount_with_igtf = payment.amount + payment.igtf_amount

    @api.depends("journal_id")
    def _compute_is_igtf(self):
        for payment in self:
            if payment.journal_id.is_igtf:
                payment.is_igtf_on_foreign_exchange = True

    @api.depends("amount", "is_igtf_on_foreign_exchange", "journal_id", "currency_id")
    def _compute_igtf_amount(self):
        for payment in self:
            if not payment.igtf_amount :
                payment.igtf_amount = 0.0
                if (
                    payment.journal_id.is_igtf
                    and payment.currency_id.id == self.env.ref("base.USD").id
                    and payment.is_igtf_on_foreign_exchange
                ):
                    payment_amount = payment.amount
                    payment.igtf_amount = payment_amount * (payment.igtf_percentage / 100)

    def _prepare_move_line_default_vals(
        self, write_off_line_vals=None, force_balance=None
    ):
        """Prepare values to create a new account.move.line for a payment.
        this method adds the igtf in the move line values to be created depending on the payment type

        Args:
            write_off_line_vals (dict, optional): Values to create the write-off account.move.line. Defaults to None.

        Returns:
            dict: Values to create the account.move.line.
        """

        vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(
            write_off_line_vals
        )

        if self.igtf_percentage == self.env.company.igtf_percentage:
            self._create_igtf_moves_in_payments(vals)

        if self.igtf_percentage == 2:
            self._create_igtf_move_supplier_two_percentage()

        return vals

    def _create_igtf_move_supplier_two_percentage(self):
        igtf_journal = self.env.company.journal_igtf_expense.id
        supplier_account = self.env.company.igtf_two_percentage_account.id
        expense_account = self.env.company.igtf_account_expense.id
        is_outbound = self.payment_type == "outbound"

        igtf_amount = self.igtf_amount
        if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
            igtf_amount = self.igtf_amount * self.foreign_rate

        move = self.env["account.move"].create(
            {
                "journal_id": igtf_journal,
                "date": self.date,
                "partner_id": self.partner_id.id,
                "manually_set_rate": True,
                "payment_igtf_id": self.id,
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
                "ref": "IGTF EXPENSE SUPPLIER" + self.name,
                "line_ids": [
                    Command.create(
                        {
                            "name": "IGTF EXPENSE SUPPLIER" + self.name,
                            "account_id": expense_account,
                            "partner_id": self.partner_id.id,
                            "amount_currency": (
                                igtf_amount if is_outbound else -igtf_amount
                            ),
                        }
                    ),
                    Command.create(
                        {
                            "name": "IGTF EXPENSE SUPPLIER" + self.name,
                            "account_id": supplier_account,
                            "partner_id": self.partner_id.id,
                            "amount_currency": (
                                -igtf_amount if is_outbound else igtf_amount
                            ),
                        }
                    ),
                ],
            }
        )

        move.action_post()
        return move

    def _create_igtf_moves_in_payments(self, vals):
        """Prepare values to create a new account.move.line for a payment.
        this method adds the igtf in the move line values to be created depending on the payment type

        Args:
            write_off_line_vals (dict, optional): Values to create the write-off account.move.line. Defaults to None.

        Returns:
            dict: Values to create the account.move.line.
        """
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )

        if self._context.get("from_pos", False):
            return

        if self._context.get("from_mobile", False):
            return

        for payment in self:
            if payment.is_igtf_on_foreign_exchange and payment.igtf_amount:
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]

                    if not vals_igtf:
                        _logger.info("IN")
                        payment._prepare_inbound_move_line_igtf_vals(vals)
                    else:
                        raise UserError(
                            _("IGTF already exists in the move line values")
                        )

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        _logger.info("OUT")
                        payment._prepare_outbound_move_line_igtf_vals(vals)
                    else:
                        raise UserError(
                            _("IGTF already exists in the move line values")
                        )

    def _create_inbound_move_line_igtf_vals(self, vals):
        """Create the igtf move line values for inbound payments
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list

        Args:
            vals (list): list of move line values

        Returns:
            list: list of move line values with the igtf move line values
        """
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        igtf_account_two_percentage = self.env.company.igtf_two_percentage_account.id
        igtf_amount = self.igtf_amount

        vals.append(
            {
                "name": "IGTF",
                "currency_id": self.currency_id.id,
                "amount_currency": -igtf_amount,
                "account_id": (
                    igtf_account
                    if self.igtf_percentage == 3
                    else igtf_account_two_percentage
                ),
                "partner_id": self.partner_id.id,
            }
        )
        return vals

    def _create_outbound_move_line_igtf_vals(self, vals):
        """
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list

        Args:
            vals (list): list of move line values

        Returns:
            list: list of move line values with the igtf move line values

        """
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        igtf_account_two_percentage = self.env.company.igtf_two_percentage_account.id
        igtf_amount = self.igtf_amount

        vals.append(
            {
                "name": "IGTF",
                "currency_id": self.currency_id.id,
                "amount_currency": igtf_amount,
                "account_id": (
                    igtf_account
                    if self.igtf_percentage == 3
                    else igtf_account_two_percentage
                ),
                "partner_id": self.partner_id.id,
            }
        )

        return vals

    def _prepare_inbound_move_line_igtf_vals(self, vals):
        """
        Prepare the igtf move line values for inbound payments
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list
        and update the credit amount of the first move line to be created to be the amount of the payment minus the igtf amount

        Args:
            vals (list): list of move line values
        """

        lines = [line for line in vals]
        if self.payment_type == "inbound":
            credit_line = lines[1]["amount_currency"] + self.igtf_amount
            credit_amount = -credit_line
            if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                credit_amount = -credit_line * self.foreign_rate
            vals[1].update({"amount_currency": credit_line, "credit": credit_amount})

            self._create_inbound_move_line_igtf_vals(vals)

    def _prepare_outbound_move_line_igtf_vals(self, vals):
        """
        Prepare the igtf move line values for inbound payments
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list
        and update the credit amount of the first move line to be created to be the amount of the payment minus the igtf amount

        Args:
            vals (list): list of move line values
        """
        lines = [line for line in vals]
        if self.payment_type == "outbound":
            debit_line = lines[1]["amount_currency"] - self.igtf_amount
            debit_amount = debit_line
            if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                debit_amount = debit_line * self.foreign_rate
            vals[1].update({"amount_currency": debit_line, "debit": debit_amount})

            self._create_outbound_move_line_igtf_vals(vals)

    def action_draft(self):
        # if payment have reconciled_invoice_ids or reconciled_bill_ids and is_igtf is True clear bi_igtf of the reconciled invoices
        def get_payment_amount_invoice(self, invoice):
            self.ensure_one()
            if invoice.bi_igtf < self.amount:
                payments = invoice.invoice_payments_widget.get("content", False)
                for payment in payments:
                    payment_id = payment.get("account_payment_id", False)
                    if not payment_id:
                        continue

                    if self.id == payment_id:
                        return abs(payment["amount"])
            return self.amount

        for payment in self:
            if (
                payment.reconciled_invoice_ids or payment.reconciled_bill_ids
            ) and payment.is_igtf_on_foreign_exchange:
                for invoice in payment.reconciled_invoice_ids:
                    if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                        invoice.bi_igtf = invoice.bi_igtf - (
                            get_payment_amount_invoice(payment, invoice)
                            * self.foreign_rate
                        )
                    else:
                        invoice.bi_igtf = invoice.bi_igtf - get_payment_amount_invoice(
                            payment, invoice
                        )

                for bill in payment.reconciled_bill_ids:
                    if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                        bill.bi_igtf = bill.bi_igtf - (
                            get_payment_amount_invoice(payment, bill)
                            * self.foreign_rate
                        )
                    else:
                        bill.bi_igtf = bill.bi_igtf - get_payment_amount_invoice(
                            payment, bill
                        )

                move = self.env["account.move"].search(
                    [("payment_igtf_id", "=", payment.id)]
                )
                if move:
                    move.button_draft()

        return super(AccountPaymentIgtf, self).action_draft()

    def get_bi_igtf(self):
        self.ensure_one()
        amount_without_difference = self.amount_with_igtf - self.igtf_amount
        if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
            amount_without_difference = amount_without_difference * self.foreign_rate

        return amount_without_difference
