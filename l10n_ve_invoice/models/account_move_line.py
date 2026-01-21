import logging

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create account move line records and validate partner assignment for payable or receivable accounts.
        This method first verifies whether the company configuration requires a partner to be assigned
        on lines associated with payable or receivable accounts. If the configuration is disabled,
        records are created normally. Otherwise, the method proceeds with the creation and then checks
        the resulting lines. If any line violates the partner requirement, a validation error is raised.
        :param vals_list: List of dictionaries containing values for new move line records.
        :return: The created recordset of account.move.line.
        :raises ValidationError: If one or more payable/receivable lines are missing a partner.
        """

        if not self.env.company.mandatory_contact_in_payable_or_receivable_accounting_accounts:
            return super().create(vals_list)

        move_lines = super().create(vals_list)

        if not move_lines._check_mandatory_partner_in_payable_or_receivable_accounts():
            raise ValidationError(_('The partner field is mandatory for accounting entries with payable or receivable accounts.'))

        return move_lines

    def write(self, vals):
        """
        Update account move line records and enforce partner assignment when applicable.
        After performing the standard write operation, this method validates whether any updated line
        associated with payable or receivable accounts is missing a partner, but only if the company
        has the mandatory configuration enabled. If validation fails, the change is reverted via
        a raised ValidationError.
        :param vals: A dictionary of values being written into the move line.
        :return: Boolean indicating success of the write operation.
        :raises ValidationError: If the update results in payable/receivable lines without a partner.
        """

        if not self.env.company.mandatory_contact_in_payable_or_receivable_accounting_accounts:
            return super().write(vals)

        res = super().write(vals)

        if not self._check_mandatory_partner_in_payable_or_receivable_accounts():
            raise ValidationError(_('The partner field is mandatory for accounting entries with payable or receivable accounts.'))

        return res

    def _check_mandatory_partner_in_payable_or_receivable_accounts(self):
        """
        Validate that all move lines with payable or receivable accounts include a partner.
        This method applies only if the company setting `mandatory_contact_in_payable_or_receivable_accounting_accounts`
        is enabled. It searches for move lines of type 'entry' that use accounts marked as
        receivable or payable and checks whether any of those lines lack a partner assignment.
        :return: True if all conditions are satisfied or the feature is disabled; False otherwise.
        """

        if not self.env.company.mandatory_contact_in_payable_or_receivable_accounting_accounts:
            return True

        if any(
            not line.partner_id for line in self.filtered(
                lambda l: l.move_id.move_type == 'entry' and l.account_id 
                and l.account_id.account_type in ['asset_receivable','liability_payable']
            )
        ):
            return False

        return True