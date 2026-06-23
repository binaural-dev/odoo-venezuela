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
    
    def _get_computed_taxes(self):
        """
        Override to determine the applicable taxes for invoice lines, specifically
        handling international sales scenarios.

        This method extends the standard tax computation by replacing the default
        taxes with the company's configured zero-aliquot taxes when the following
        conditions are met:
            - The move is a sale document (including receipts).
            - The journal is marked as an international sale.

        If these conditions are not satisfied, the method falls back to the default
        tax computation provided by the parent implementation.

        Additionally, the resulting taxes are filtered to ensure they belong to the
        same company as the invoice.

        Returns:
            recordset: A recordset of `account.tax` representing the applicable taxes.
        """

        tax_ids = super()._get_computed_taxes()

        is_sale_international = self.move_id.journal_id.is_sale_international

        if not self.move_id.is_sale_document(include_receipts=True) or not is_sale_international:
            return tax_ids
        
        company_domain = self.env['account.tax']._check_company_domain(self.move_id.company_id)
        filtered_taxes_id = self.env.company.zero_aliquot_sale_international.filtered_domain(company_domain)
        tax_ids = filtered_taxes_id or self.product_id.taxes_id.filtered_domain(company_domain)

        return tax_ids