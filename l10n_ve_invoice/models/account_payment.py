import logging

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create payment records and validate mandatory partner assignment where applicable.
        If the company configuration requires that payable or receivable related records must
        have a partner assigned, this method ensures the rule is enforced. The payments are created
        first, and then validation is applied. If any resulting payment references a payable or
        receivable account without an assigned partner, a ValidationError is raised.
        :param vals_list: List of dictionaries containing values for the new payment records.
        :return: The created recordset of account.payment.
        :raises ValidationError: If any payable/receivable related payment lacks a partner.
        """

        if not self.env.company.mandatory_contact_in_payable_or_receivable_accounting_accounts:
            return super().create(vals_list)

        payments = super().create(vals_list)

        if not self._check_mandatory_partner_in_payable_or_receivable_accounts():
            raise ValidationError(_('The partner field is mandatory for payments with payable or receivable accounts.'))

        return payments

    def write(self, vals):
        """
        Update payment records and enforce mandatory partner validation when required.
        After applying the write operation, this method checks whether the updated payment records
        reference payable or receivable accounts and ensures a partner is assigned, provided the
        company configuration enforces this requirement. If validation fails, a ValidationError
        is raised, preventing the inconsistent modification.
        :param vals: A dictionary of values being written to the payment records.
        :return: Boolean indicating success of the write operation.
        :raises ValidationError: If the update results in a payable/receivable payment without a partner.
        """

        if not self.env.company.mandatory_contact_in_payable_or_receivable_accounting_accounts:
            return super().write(vals)

        res = super().write(vals)

        if not self._check_mandatory_partner_in_payable_or_receivable_accounts():
            raise ValidationError(_('The partner field is mandatory for payments with payable or receivable accounts.'))

        return res

    def _check_mandatory_partner_in_payable_or_receivable_accounts(self):
        """
        Verify that payments associated with payable or receivable accounts have a partner assigned.
        The validation applies only when the company configuration 
        `mandatory_contact_in_payable_or_receivable_accounting_accounts` is enabled. The method
        evaluates payments whose destination accounts are marked as receivable or payable, and
        checks that the partner field is present.
        :return: True if validation passes or the configuration is disabled; False otherwise.
        """

        if not self.env.company.mandatory_contact_in_payable_or_receivable_accounting_accounts:
            return True

        if any(
            not payment.partner_id for payment in self.filtered(
                lambda p: p.destination_account_id 
                and p.destination_account_id.account_type in ['asset_receivable','liability_payable']
            )
        ):
            return False

        module_name = 'binaural_advance_payment'

        module = self.env['ir.module.module'].sudo().search([('name', '=', module_name)], limit=1)

        if module and module.state == 'installed':

            if any(
                not payment.partner_id for payment in self.filtered(
                    lambda p: p.is_advance_payment
                )
            ):
                raise ValidationError(_('The partner field is mandatory for advance payments'))

        return True