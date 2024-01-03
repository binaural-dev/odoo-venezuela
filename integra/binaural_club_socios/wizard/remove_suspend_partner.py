from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import logging

_logger = logging.getLogger()

class RemoveSuspendPartner(models.TransientModel):
    _name = "remove.suspend.partner"

    partner_to_remove_suspend = fields.Many2one("res.partner", string="Socio a remover suspensión")

    def remove_suspend_auto(self):
        partners_to_remove = self.env["res.partner"].search(
            [
                ("active", "=", True),
                ("can_access_club", "=", False),
                ("end_date_suspend", "=", fields.Date.today()),
            ]
        )
        for partner in partners_to_remove:
            partner.write(
                {
                    "date_remove_suspend": fields.Date.today(),
                    "can_access_club": True,
                    "user_remove_suspend": self.env.uid,
                    "state_partner": partner.prev_state_partner,
                    "prev_state_partner": partner.state_partner,
                }
            )
            if partner.type == "contact" and partner.parent_id:
                partner.parent_id.message_post(
                    subject=_("Suspension removed:(%s)") % partner.name,
                    body=_("Suspension of the family charge %s removed on: %s, Automatically")
                    % (
                        partner.name,
                        fields.Date.today().strftime("%d/%m/%y"),
                    ),
                )
            else:
                partner.message_post(
                    subject=_("Suspension removed:(%s)") % partner.name,
                    body=_("Suspension of the partner %s removed on: %s, Automatically")
                    % (
                        partner.name,
                        fields.Date.today().strftime("%d/%m/%y"),
                    ),
                )

    def remove_suspend_partner(self):
        if not self.partner_to_remove_suspend:
            raise UserError(_("Partner to remove suspension is required"))
        self.partner_to_remove_suspend.write(
            {
                "date_remove_suspend": fields.Date.today(),
                "can_access_club": True,
                "user_remove_suspend": self.env.uid,
                "state_partner": self.partner_to_remove_suspend.prev_state_partner,
                "prev_state_partner": self.partner_to_remove_suspend.state_partner,
            }
        )

        if (
            self.partner_to_remove_suspend.type == "contact"
            and self.partner_to_remove_suspend.parent_id
        ):
            self.partner_to_remove_suspend.parent_id.message_post(
                subject=_("Suspension removed:(%s)") % self.partner_to_remove_suspend.name,
                body=_(
                    "Suspension of the family charge %s removed on: %s, by user %s manually"
                )
                % (
                    self.partner_to_remove_suspend.name,
                    fields.Date.today().strftime("%d/%m/%y"),
                    self.env.user.name,
                ),
            )
        else:
            self.partner_to_remove_suspend.message_post(
                subject=_("Suspension removed:(%s)") % self.partner_to_remove_suspend.name,
                body=_("Suspension of the partner %s removed on: %s, by user %s manually")
                % (
                    self.partner_to_remove_suspend.name,
                    fields.Date.today().strftime("%d/%m/%y"),
                    self.env.user.name,
                ),
            )
