from odoo import models, api, exceptions, fields, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from datetime import timedelta

import logging
_logger = logging.getLogger(__name__)


class ActionPartner(models.Model):
    _inherit = "action.partner"


    @api.onchange("state")
    def _onchange_is_membership_active(self):
        """
        Onchange method to update the suspended_membership field
        based on the state of the membership.
        """
        if self.state == "active":
            self.suspended_membership = False

        if self.state == "suspended":
            self.suspended_membership = True

    def _cron_suspend_club_members(self):
        """
        Cron job to automatically suspend active memberships
        based on overdue payments.
        """
        try:
            company = self.env.company
            active_memberships = self.env['action.partner'].search([
                ('state', '=', 'active')
            ])
            delay_days = company.membership_suspension_delay_days
            today = fields.Date.today()

            cutoff_date = today - timedelta(days=delay_days)

            for membership in active_memberships:
                owner_partner = membership.owner_id
                membership_type_product = membership.membership_type_plan.product_id
                                
                overdue_invoices = self.env['account.move'].search([
                    ('partner_id', '=', owner_partner.id),
                    ('state', '=', 'posted'),
                    ('move_type', '=', 'out_invoice'),
                    ('payment_state', '!=', 'paid'),
                    ('invoice_line_ids.product_id', '=', membership_type_product.id),
                    ('invoice_date_due', '<=', cutoff_date)
                ])

                if not overdue_invoices:
                    continue

                membership.suspended_membership = True
                membership.last_suspension_date = today


        except Exception as e:
            _logger.error(f"Error en el cron _cron_suspend_club_members: {e}", exc_info=True)
            
        return True