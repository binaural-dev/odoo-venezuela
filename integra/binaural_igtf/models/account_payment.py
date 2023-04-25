from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"

    def default_is_igtf(self):
        return self.env.company.is_igtf or False

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
        digits=(16, 1),
    )

    igtf_amount = fields.Float(
        string="IGTF Amount",
        compute="_compute_igtf_amount",
        store=True,
        help="IGTF Amount",
        digits=(16, 2),
    )

    amount_with_igtf = fields.Float(
        string="Amount with IGTF", compute="_compute_amount_with_igtf", store=True
    )

    @api.depends("amount", "is_igtf", "igtf_amount")
    def _compute_amount_with_igtf(self):
        for payment in self:
            if not payment.amount_with_igtf:
                payment.amount_with_igtf = payment.amount + payment.igtf_amount

    @api.depends("journal_id", "is_igtf")
    def _compute_is_igtf(self):
        for payment in self:
            if payment.journal_id.is_igtf and payment.journal_id.fiscal and payment.is_igtf:
                payment.is_igtf_on_foreign_exchange = True

    @api.depends("amount", "is_igtf")
    def _compute_igtf_amount(self):
            for payment in self:
                if not payment.igtf_amount:
                    payment.igtf_amount = 0.0
                    if payment.is_igtf and payment.journal_id.is_igtf and payment.journal_id.fiscal:
                        payment.igtf_amount = payment.amount * (payment.igtf_percentage / 100)


    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        """Prepare values to create a new account.move.line for a payment.
        this method adds the igtf in the move line values to be created depending on the payment type

        Args:
            write_off_line_vals (dict, optional): Values to create the write-off account.move.line. Defaults to None.

        Returns:
            dict: Values to create the account.move.line.
        """
        vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(write_off_line_vals)
        igtf_account = self.env.company.customer_account_igtf_id.id if self.partner_type == "customer" else self.env.company.supplier_account_igtf_id.id

        for payment in self:
        
            if payment.is_igtf and payment.igtf_amount and payment.is_igtf_on_foreign_exchange:
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x['account_id'] == igtf_account]
                    
                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals)    
                    else:
                        raise UserError(_("IGTF already exists in the move line values"))
                        
                    
                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x['account_id'] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals)
                    else:
                        raise UserError(_("IGTF already exists in the move line values"))

        return vals

    def _create_inbound_move_line_igtf_vals(self, vals):
        """Create the igtf move line values for inbound payments
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list

        Args:
            vals (list): list of move line values

        Returns:
            list: list of move line values with the igtf move line values
        """
        igtf_account = self.env.company.customer_account_igtf_id.id if self.partner_type == "customer" else self.env.company.supplier_account_igtf_id.id
        igtf_amount = self.igtf_amount

        vals.append(
            {
                "name": "IGTF",
                "debit": 0,
                "credit": igtf_amount,
                "amount_currency": -igtf_amount,
                "account_id": igtf_account,
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
        igtf_account = self.env.company.customer_account_igtf_id.id if self.partner_type == "customer" else self.env.company.supplier_account_igtf_id.id
        igtf_amount = self.igtf_amount
        
        vals.append(
            {
                "name": "IGTF",
                "debit": igtf_amount,
                "credit": 0,
                "amount_currency": igtf_amount,
                "account_id": igtf_account,
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
            credit_line = lines[1]["credit"] - self.igtf_amount
            vals[1].update({"amount_currency": -credit_line, "credit": credit_line})    
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
            debit_line = lines[1]["debit"] - self.igtf_amount
            vals[1].update({"amount_currency": debit_line, "debit": debit_line})
            self._create_outbound_move_line_igtf_vals(vals)


    def action_draft(self):
        # if payment have reconciled_invoice_ids or reconciled_bill_ids and is_igtf is True clear bi_igtf of the reconciled invoices
        for payment in self:
            if payment.reconciled_invoice_ids or payment.reconciled_bill_ids and payment.is_igtf:
                for invoice in payment.reconciled_invoice_ids:
                    invoice.bi_igtf = invoice.bi_igtf - payment.amount
                for bill in payment.reconciled_bill_ids:
                    bill.bi_igtf = bill.bi_igtf - payment.amount

        return super(AccountPaymentIgtf, self).action_draft()
