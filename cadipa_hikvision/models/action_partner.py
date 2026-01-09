from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class ActionPartner(models.Model):
    _inherit = "action.partner"


    def action_sync_owner_to_hikcentral(self):
        """
        Manual synchronization of the Owner to HikCentral.
        """
        if not self.membership_start_date or not self.membership_end_date:
            raise ValidationError(_("Membership start and end dates must be defined."))

        for record in self:
            if record.owner_id:
                record._sync_owner_to_hikcentral()

    def cancel_membership(self):
        """
        Override to use fast revocation on membership cancellation.
        """
        super(ActionPartner, self).cancel_membership()

        for record in self:
            if record.owner_id:
                hik_user = self.env["hikcentral.users"].search(
                    [("partner_id", "=", record.owner_id.id)], limit=1
                )
                if hik_user:
                    hik_user.action_revoke_access()

            for beneficiary in record.beneficiary_partner_ids:
                if beneficiary.guest_state == "confirmed":
                    ben_hik_user = self.env["hikcentral.users"].search(
                        [("partner_id", "=", beneficiary.id)], limit=1
                    )
                    if ben_hik_user:
                        ben_hik_user.action_revoke_access()

    @api.constrains("suspended_membership", "state")
    def _check_suspended_membership(self):
        super(ActionPartner, self)._check_suspended_membership()

        for record in self:
            HikUsers = self.env["hikcentral.users"]

            if record.state == 'draft':
                continue

            if record.state in ["suspended", "canceled"] or record.suspended_membership:
                if record.owner_id:
                    owner_hik = HikUsers.search(
                        [("partner_id", "=", record.owner_id.id)], limit=1
                    )
                    if owner_hik:
                        owner_hik.action_revoke_access()

                for beneficiary in record.beneficiary_partner_ids:
                    if beneficiary.guest_state == "confirmed":
                        ben_hik = HikUsers.search(
                            [("partner_id", "=", beneficiary.id)], limit=1
                        )
                        if ben_hik:
                            ben_hik.action_revoke_access()

            else:
                real_end_date = record.membership_end_date or (
                    fields.Date.today() + relativedelta(years=1)
                )

                if record.owner_id:
                    owner_hik = HikUsers.search(
                        [("partner_id", "=", record.owner_id.id)], limit=1
                    )

                    if owner_hik:
                        owner_hik.action_restore_access(real_end_date)
                    else:
                        record._sync_owner_to_hikcentral()

                for beneficiary in record.beneficiary_partner_ids:
                    beneficiary.action_restore_beneficiary_fast(real_end_date)

    def _sync_owner_to_hikcentral(self):
        """
        Orchestrator for FULL synchronization (Create / Update / Reactivate).
        """
        self.ensure_one()
        HikUsers = self.env["hikcentral.users"]

        if self.state in ["suspended", "canceled"]:
            hik_user = HikUsers.search([("partner_id", "=", self.owner_id.id)], limit=1)
            if hik_user:
                hik_user.action_revoke_access()
                return

        try:
            vals = self._prepare_hikcentral_owner_values()

            hik_user = HikUsers.search([("partner_id", "=", self.owner_id.id)], limit=1)

            if hik_user:
                vals["state"] = "synced"
                hik_user.write(vals)
            else:
                hik_user = HikUsers.create(vals)

            hik_user.sync_user_with_hikcentral()

            _logger.info(
                f"Owner {self.owner_id.name} successfully synchronized with HikCentral."
            )

        except Exception as e:
            _logger.error(
                f"Error in HikCentral synchronization for {self.owner_id.name}: {str(e)}"
            )

    def _prepare_hikcentral_owner_values(self):
        """
        Computes values for Owner. Contains logic for Dates.
        """
        self.ensure_one()
        HikDepartments = self.env["hikcentral.department"]
        HikAccessLevels = self.env["hikcentral.access.level"]

        start_date = self.membership_start_date or fields.Date.today()

        if self.state in ["suspended", "canceled"]:
            end_date = fields.Date.today()
        else:
            end_date = self.membership_end_date or (
                fields.Date.today() + relativedelta(years=1)
            )

        default_department = HikDepartments.search(
            [("default_membership_dept", "=", True)], limit=1
        )

        department_id = False
        if self.membership_type_plan.hikcentral_department_id:
            department_id = self.membership_type_plan.hikcentral_department_id.id
        elif default_department:
            department_id = default_department.id

        if not department_id:
            raise UserError(
                _(
                    "No HikCentral department defined for membership plan '%s' and no default department set in HikCentral departments."
                )
                % self.membership_type_plan.name
            )

        default_access_levels = HikAccessLevels.search(
            [("default_membership_access_level", "=", True)]
        )

        if not default_access_levels:
            raise UserError(
                _(
                    "No default HikCentral access levels for memberships defined. Please set one access level as default for memberships."
                )
            )

        return {
            "partner_id": self.owner_id.id,
            "is_visitor": False,
            "start_date": start_date,
            "comment": self.number,
            "end_date": end_date,
            "department_id": department_id,
            "access_level_ids": [(6, 0, default_access_levels.ids)],
        }
