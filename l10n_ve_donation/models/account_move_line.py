from odoo import _, fields, models, api
from odoo.exceptions import ValidationError, UserError

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        """The new lines of a donation entry take the company partner (see
        `account.move._fill_donation_entry_line_partner()`). It is done after
        the creation and not in the compute of the field: the web client
        sends `partner_id: False` for the lines it creates, and a value in
        the creation values is not computed."""
        lines = super().create(vals_list)
        lines.move_id._fill_donation_entry_line_partner()
        lines.move_id._mark_donation_received_from_statement()
        return lines

    def write(self, vals):
        """Reconciling a bank statement line changes the account of its
        suspense line: if it becomes a received donations account, the entry
        is a donation received (see
        `account.move._mark_donation_received_from_statement()`)."""
        res = super().write(vals)
        if vals.keys() & {"account_id", "debit", "credit", "balance", "amount_currency"}:
            self.move_id._mark_donation_received_from_statement()
        return res

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        """
        Override to allow expenses accounts to be used in donations in the
        account of the account.move.
        """
        for line in self:
            account_type = line.account_id.account_type
            if line.move_id.is_sale_document(include_receipts=True):
                if account_type == 'liability_payable':
                    raise UserError(_("Account %s is of payable type, but is used in a sale operation.", line.account_id.code))
                
                is_receivable_type = account_type == 'asset_receivable'
                if line.move_id.is_donation:
                    donation_account = line.company_id.donation_account_id or self.env.company.donation_account_id
                    if donation_account and line.account_id == donation_account and line.display_type == 'payment_term':
                        is_receivable_type = True

                if (line.display_type == 'payment_term') ^ is_receivable_type:
                    raise UserError(_("Any journal item on a receivable account must have a due date and vice versa."))
            if line.move_id.is_purchase_document(include_receipts=True):
                if account_type == 'asset_receivable':
                    raise UserError(_("Account %s is of receivable type, but is used in a purchase operation.", line.account_id.code))
                if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                    raise UserError(_("Any journal item on a payable account must have a due date and vice versa."))