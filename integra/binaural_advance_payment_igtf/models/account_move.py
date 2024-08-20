import logging
from odoo import api, fields, models, _, Command

_logger = logging.getLogger(__name__)


class AccountMoveAdvanceIgtf(models.Model):
    _inherit = "account.move"

    def default_igtf_percentage(self):
        return self.env.company.igtf_percentage or 0.0

    is_advance_move = fields.Boolean(
        string="Is Advance Move?",
        store=True,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage", store=True, default=default_igtf_percentage
    )

    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        lines = self.env["account.move.line"].browse(line_id)
        move_advance = lines["move_id"].is_advance_move
        if move_advance:
            move = self._create_advance_payment_move(lines)
            return self._reconcile_move_with_payment_difference(lines["move_id"], move)
        return super().js_assign_outstanding_line(line_id)

    def _create_advance_payment_move(self, lines_id):
        """
        This method is called when click on add payment widget. It will create a move to reconcile with the payment difference

        Args:
            lines_id (account.move.line): Move line object

        Returns:
            account.move: Move object
        """

        amount_currency = 0
        amount_currency_with_igtf = 0

        advance_journal = self.env.company.advance_payment_igtf_journal_id.id

        for move in self:
            advance_account_id = (
                self.env.company.advance_customer_account_id.id
                if move.move_type == "out_invoice"
                else self.env.company.advance_supplier_account_id.id
            )

            partner_account_id = (
                move.partner_id.property_account_receivable_id.id
                if move.move_type == "out_invoice"
                else move.partner_id.property_account_payable_id.id
            )

            igtf_account_id = (
                self.env.company.customer_account_igtf_id.id
                if move.move_type in ("out_invoice", "in_refund")
                else self.env.company.supplier_account_igtf_id.id
            )

            amount_account_receivable = move.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            ).balance

            amount_account_receivable_with_igtf = amount_account_receivable * (
                move.igtf_percentage / 100
            )

            if amount_account_receivable < -lines_id["amount_residual"]:
                amount_with_igtf = amount_account_receivable + amount_account_receivable_with_igtf

                if -lines_id["amount_residual"] < amount_with_igtf:
                    amount_filtered = -lines_id["amount_residual"]
                    amount_currency_igtf = amount_account_receivable * (move.igtf_percentage / 100)
                    amount_currency = amount_filtered
                    amount = amount_filtered - amount_currency_igtf
                    amount_currency_with_igtf = amount_currency_igtf

                    # Set the IGTF Value
                    move.bi_igtf = amount_account_receivable

                else:
                    amount_filtered = move.line_ids.filtered(
                        lambda line: line.account_id.account_type == "asset_receivable"
                    ).amount_currency
                    
                    amount_currency_igtf = amount_filtered * (move.igtf_percentage / 100)
                    amount_currency = amount_filtered + amount_currency_igtf
                    amount = amount_filtered
                    amount_currency_with_igtf = amount_currency_igtf

                    #Set the IGTF Value
                    move.bi_igtf = amount_filtered


            else:
                amount_filtered = -lines_id["amount_residual"]
                amount_currency_igtf = amount_filtered * (move.igtf_percentage / 100)
                amount_currency = amount_filtered
                amount = amount_filtered - amount_currency_igtf
                amount_currency_with_igtf = amount_currency_igtf

                # Set the IGTF Value
                move.bi_igtf = amount_filtered

            move_line_ids = [
                Command.create(
                    {
                        "account_id": advance_account_id,
                        "amount_currency": amount_currency,
                    },
                ),
                Command.create(
                    {
                        "account_id": partner_account_id,
                        "amount_currency": -amount,
                    },
                ),
                Command.create(
                    {
                        "account_id": igtf_account_id,
                        "amount_currency": -amount_currency_with_igtf,
                    },
                ),
            ]

            move_to_reconcile_with_payment_difference = self.env["account.move"].create(
                {
                    "journal_id": advance_journal,
                    "date": move.invoice_date,
                    "partner_id": self.partner_id.id,
                    "vat": self.partner_id.vat,
                    "ref": "CRUCE DE ANTICIPO",
                    "line_ids": move_line_ids,
                }
            )

        return move_to_reconcile_with_payment_difference
    
    def _reconcile_move_with_payment_difference(self, move_id, move_to_reconcile):
        """
        This method is called when click on add payment widget. It will reconcile the move with the payment difference

        Args:
            move_id (account.move): Move object to reconmove_to_reconcilecile
            move_to_reconcile (account.move): Move object to reconcile with

        Returns:
            bool: True
        """

        move_to_reconcile.action_post()

        if self.move_type == "out_invoice":
            advance_lines = move_id.line_ids.filtered(
                lambda x: x.account_id.id == self.env.company.advance_customer_account_id.id 
            )

            move_to_reconcile_lines = move_to_reconcile.line_ids.filtered(
                lambda x: x.account_id.id == self.env.company.advance_customer_account_id.id
            )

        elif self.move_type == "in_invoice":
            advance_lines = move_id.line_ids.filtered(
                lambda x: x.account_id.id == self.env.company.advance_supplier_account_id.id 
            )

            move_to_reconcile_lines = move_to_reconcile.line_ids.filtered(
                lambda x: x.account_id.id == self.env.company.advance_supplier_account_id.id
            )

        move_line_to_reconcile = self.env["account.move.line"].browse([move_to_reconcile_lines.id])
        move_line_to_reconcile += advance_lines
        move_line_to_reconcile.reconcile()

        move_to_reconcile_asset_account = move_to_reconcile.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable" or x.account_id.account_type == "liability_payable"
        )

        move_account_asset = self.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable" or x.account_id.account_type == "liability_payable"
        )

        move_reconcile = self.env["account.move.line"].browse([move_to_reconcile_asset_account.id])
        move_reconcile += move_account_asset
        move_reconcile.reconcile()

        return True
