import logging
from odoo import api, fields, models, _, Command

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payments(self):
        """
        This method is called when the wizard is submitted. It will create a move to reconcile with the payment difference

        Returns:
            list: account.payment
        """
        payments = super()._create_payments()

        for payment in payments:
            partner_account_id = (
                payment.partner_id.property_account_receivable_id.id
                if payment.partner_type == "customer"
                else payment.partner_id.property_account_payable_id.id
            )

            payment_invoice_amount = payment.line_ids.filtered(
                lambda line: line.account_id.id == partner_account_id
            ).balance

            if (
                payment.amount > -payment_invoice_amount
                and payment.journal_id.fiscal
                and payment.journal_id.is_igtf
            ):
                move_to_reconcile_with_payment_difference = (
                    self._create_move_to_reconcile_with_payment_difference(payment)
                )
                move_to_reconcile_with_payment_difference.action_post()

                self._reconcile_payment_and_move_lines(
                    payment, move_to_reconcile_with_payment_difference
                )

        return payments

    def _create_move_to_reconcile_with_payment_difference(self, payment):
        """
        Create a move to reconcile with the payment difference

        Args:
            payment (account.payment): Payment object

        Returns:
            account.move: Move object
        """
        advance_account_id = (
            self.env.company.advance_customer_account_id.id
            if payment.partner_type == "customer"
            else self.env.company.advance_supplier_account_id.id
        )

        partner_account_id = (
            payment.partner_id.property_account_receivable_id.id
            if payment.partner_type == "customer"
            else payment.partner_id.property_account_payable_id.id
        )

        invoice_amount = payment.reconciled_invoice_ids.line_ids.filtered(
            lambda line: line.account_id.id == partner_account_id
        ).amount_currency
        asset_amout = payment.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ).amount_currency

        amount_currency = asset_amout + invoice_amount

        payment_line_ids = [
            Command.create(
                {
                    "account_id": advance_account_id,
                    "amount_currency": amount_currency,
                },
            ),
            Command.create(
                {
                    "account_id": partner_account_id,
                    "amount_currency": -amount_currency,
                },
            ),
        ]

        move_to_reconcile_with_payment_difference = self.env["account.move"].create(
            {
                "journal_id": self.env.company.advance_payment_igtf_journal_id.id,
                "date": payment.date,
                "partner_id": payment.partner_id.id,
                "vat": payment.partner_id.vat,
                "ref": "RESTANTE DE PAGO EN DIVISA" + "(" + payment.name + ")",
                "is_advance_move": True,
                "line_ids": payment_line_ids,
            }
        )

        return move_to_reconcile_with_payment_difference

    def _reconcile_payment_and_move_lines(self, payment, move):
        """
        Reconcile payment and move lines

        Args:
            payment (account.payment): Payment object
            move (account.move): Move object
        """
        asset_receivable_lines = move.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable"
        )
        payment_line = payment.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable"
        )

        payment_line_to_reconcile = self.env["account.move.line"].browse([payment_line.id])

        payment_line_to_reconcile += asset_receivable_lines

        payment_line_to_reconcile.reconcile()
