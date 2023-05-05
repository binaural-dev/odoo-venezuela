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

    @api.depends(
        "journal_id", "partner_id", "partner_type", "is_internal_transfer", "is_advance_payment"
    )
    def _compute_destination_account_id(self):
        customer_account = self.env.company.advance_customer_account_id.id
        supplier_account = self.env.company.advance_supplier_account_id.id
        if not customer_account or not supplier_account:
            raise UserError(
                _(
                    "You must configure the advance customer account and the advance supplier account in the company settings"
                )
            )
        if self.is_advance_payment:
            if self.partner_type == "customer":
                self.destination_account_id = customer_account
                return
            elif self.partner_type == "supplier":
                self.destination_account_id = supplier_account
                return
        else:
            return super(AccountPayment, self)._compute_destination_account_id()

    def _seek_for_lines(self):
        """Helper used to dispatch the journal items between:
        - The lines using the temporary liquidity account.
        - The lines using the counterpart account.
        - The lines being the write-off lines.
        :return: (liquidity_lines, counterpart_lines, writeoff_lines)

        this method is overriden to allow the use of advance payment accounts in counterpart lines
        the counterpart lines are the lines that are not liquidity lines and not writeoff lines

        """
        self.ensure_one()

        liquidity_lines = self.env["account.move.line"]
        counterpart_lines = self.env["account.move.line"]
        writeoff_lines = self.env["account.move.line"]

        for line in self.move_id.line_ids:
            if line.account_id in self._get_valid_liquidity_accounts():
                liquidity_lines += line


                
            elif (
                line.account_id.account_type in ("asset_receivable", "liability_payable", "liability_current")
                or line.partner_id == line.company_id.partner_id
            ):
                counterpart_lines = line

            else:
                writeoff_lines += line

        return liquidity_lines, counterpart_lines, writeoff_lines


    def _synchronize_from_moves(self, changed_fields):
        """Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.


        this method is overriden to allow the use of advance payment accounts in counterpart lines
        now the counterpart lines allowed accounts types asset_current, that is the advance payment account type

        """
        if self._context.get("skip_account_move_synchronization"):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):
            # After the migration to 14.0, the journal entry could be shared between the account.payment and the
            # account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
            if pay.move_id.statement_line_id:
                continue

            move = pay.move_id
            move_vals_to_write = {}
            payment_vals_to_write = {}

            if "journal_id" in changed_fields:
                if pay.journal_id.type not in ("bank", "cash"):
                    raise UserError(_("A payment must always belongs to a bank or cash journal."))

            if "line_ids" in changed_fields:
                all_lines = move.line_ids
                liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                if len(liquidity_lines) != 1:
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "include one and only one outstanding payments/receipts account.",
                            move.display_name,
                        )
                    )

                if len(counterpart_lines) != 1:
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "include one and only one receivable/payable account (with an exception of "
                            "internal transfers).",
                            move.display_name,
                        )
                    )

                if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "share the same currency.",
                            move.display_name,
                        )
                    )

                if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                    raise UserError(
                        _(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "share the same partner.",
                            move.display_name,
                        )
                    )

                if (
                    counterpart_lines.account_id.account_type == "asset_receivable"
                    or counterpart_lines.account_id.account_type == "liability_current"
                ):
                    partner_type = "customer"
                else:
                    partner_type = "supplier"

                liquidity_amount = liquidity_lines.amount_currency

                move_vals_to_write.update(
                    {
                        "currency_id": liquidity_lines.currency_id.id,
                        "partner_id": liquidity_lines.partner_id.id,
                    }
                )
                payment_vals_to_write.update(
                    {
                        "amount": abs(liquidity_amount),
                        "partner_type": partner_type,
                        "currency_id": liquidity_lines.currency_id.id,
                        "destination_account_id": counterpart_lines.account_id.id,
                        "partner_id": liquidity_lines.partner_id.id,
                    }
                )
                if liquidity_amount > 0.0:
                    payment_vals_to_write.update({"payment_type": "inbound"})
                elif liquidity_amount < 0.0:
                    payment_vals_to_write.update({"payment_type": "outbound"})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))
