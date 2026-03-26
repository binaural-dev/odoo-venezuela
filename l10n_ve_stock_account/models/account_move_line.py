from odoo import _, fields, models, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    from_picking_line = fields.Boolean(string="From Picking", default=False)

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
    


