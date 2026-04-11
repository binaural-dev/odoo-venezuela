from odoo import models, api, fields, _
from odoo.exceptions import UserError
from datetime import datetime, time as py_time
from zoneinfo import ZoneInfo
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def sync_beneficiary_to_hikcentral(self):
        """
        Public method to manually sync beneficiary to HikCentral.
        """
        for partner in self:
            if not partner.guest_state == "confirmed" and partner.associate_action:
                raise UserError(
                    _("Only confirmed beneficiaries linked to an action can be synced.")
                )
            partner._sync_beneficiary_to_hikcentral()

    def remove_beneficiary_from_hikcentral(self):
        """
        Public method to manually remove beneficiary from HikCentral.
        """
        for partner in self:
            hik_users = self.env["hikcentral.users"].search(
                [("partner_id", "=", partner.id)]
            )
            if not hik_users:
                raise UserError(
                    _(
                        "No HikCentral user found for beneficiary %s. Please sync the beneficiary first."
                    )
                    % partner.name
                )

            for hik_user in hik_users:
                hik_user.action_revoke_access()

    def action_cancel_beneficiary(self):
        """
        Public method for action.partner to cancel beneficiary access.
        """
        res = super(ResPartner, self).action_cancel_beneficiary()

        for partner in self:
            hik_users = self.env["hikcentral.users"].search(
                [("partner_id", "=", partner.id)]
            )

            if not hik_users:
                _logger.warning(
                    f"No HikCentral user found for beneficiary {partner.name}. Skipping revocation."
                )
                continue

            for hik_user in hik_users:
                hik_user.action_revoke_access()

        return res

    def action_sync_hikcentral_beneficiary(self):
        """
        Public method required by action.partner.
        Used for the suspension/reactivation cascade.
        """
        for partner in self:
            if partner.guest_state == "confirmed" and partner.associate_action:
                partner._sync_beneficiary_to_hikcentral()

    def action_restore_beneficiary_fast(self, new_end_date):
        """
        Public method for action.partner to quickly restore beneficiaries.
        """
        for partner in self:
            if partner.guest_state != "confirmed":
                continue

            hik_users = self.env["hikcentral.users"].search(
                [("partner_id", "=", partner.id)]
            )
            for hik_user in hik_users:
                hik_user.action_restore_access(new_end_date)

    def _sync_beneficiary_to_hikcentral(self):
        self.ensure_one()
        HikUsers = self.env["hikcentral.users"]
        membership = self.associate_action

        parent_hik_user = membership.owner_id and HikUsers.search(
            [("partner_id", "=", membership.owner_id.id)], limit=1
        )

        if membership.owner_id and not parent_hik_user:
            _logger.warning(
                f"Owner {membership.owner_id.name} has no HikCentral user. {self.name} might handle defaults."
            )

        vals = self._prepare_hikcentral_values(membership, parent_hik_user)

        existing_user = HikUsers.search([("partner_id", "=", self.id)], limit=1)
        if existing_user:
            vals["state"] = "synced"
            existing_user.write(vals)
            user_record = existing_user
        else:
            user_record = HikUsers.create(vals)

        user_record.sync_user_with_hikcentral()
        _logger.info(f"Beneficiary {self.name} synced.")

    def _prepare_hikcentral_values(self, membership, parent_hik_user):
        self.ensure_one()
        HikDepartments = self.env["hikcentral.department"]
        HikAccessLevels = self.env["hikcentral.access.level"]

        start_date = membership.membership_start_date or fields.Date.today()

        if (
            membership.state in ["suspended", "canceled"]
            or membership.suspended_membership
        ):
            end_date = fields.Date.today()
        else:
            end_date = membership.membership_end_date or fields.Date.today().replace(
                year=fields.Date.today().year + 1
            )

        vz_tz = ZoneInfo("America/Caracas")
        utc_tz = ZoneInfo("UTC")

        start_dt_naive = datetime.combine(start_date, py_time(0, 0, 0))
        start_date_db = start_dt_naive.replace(tzinfo=vz_tz).astimezone(utc_tz).replace(tzinfo=None)

        end_dt_naive = datetime.combine(end_date, py_time(23, 59, 59))
        end_date_db = end_dt_naive.replace(tzinfo=vz_tz).astimezone(utc_tz).replace(tzinfo=None)

        default_department = HikDepartments.search(
            [("default_membership_dept", "=", True)], limit=1
        )

        parent_dept_id = (
            parent_hik_user.department_id.id
            if (parent_hik_user and parent_hik_user.department_id)
            else False
        )

        department_id = parent_dept_id if parent_dept_id else default_department.id

        if not department_id:
            raise UserError(_("No HikCentral department available for beneficiary."))

        default_access_levels = HikAccessLevels.search(
            [("default_membership_access_level", "=", True)]
        )
        if not default_access_levels:
            raise UserError(_("No default access levels defined."))

        ids_to_assign = []
        if parent_hik_user and parent_hik_user.access_level_ids:
            ids_to_assign = parent_hik_user.access_level_ids.ids
        else:
            ids_to_assign = default_access_levels.ids

        return {
            "partner_id": self.id,
            "is_visitor": False,
            "start_date": start_date_db,
            "end_date": end_date_db,
            "parent_user_id": parent_hik_user.id if parent_hik_user else False,
            "department_id": department_id,
            "access_level_ids": [(6, 0, ids_to_assign)],
        }
