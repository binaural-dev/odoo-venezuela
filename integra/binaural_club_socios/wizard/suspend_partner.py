from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class SuspendPartner(models.TransientModel):
    _name = "suspend.partner"

    reason = fields.Text(string="Reason")

    end_date_suspend = fields.Date(string="End date suspend")

    partner_to_suspend = fields.Many2one("res.partner", string="Partner to suspend")

    def suspend_partner(self):
        if not self.reason:
            raise UserError("Required Reason")
        if not self.end_date_suspend:
            raise UserError("Required end date suspend")
        if self.end_date_suspend <= fields.Date.today():
            raise UserError("The final date of suspension must be greater than the current date.")
        if not self.partner_to_suspend:
            raise UserError("Required partner to suspend")

        self.partner_to_suspend.write(
            {
                "can_access_club": False,
                "reason": self.reason,
                "end_date_suspend": self.end_date_suspend,
                "start_date_suspend": fields.Date.today(),
                "user_suspend": self.env.uid,
                "prev_state_partner": self.partner_to_suspend.state_partner,
            }
        )  #'state_partner':'discontinued'
        self.partner_to_suspend.message_post(
            subject=_("Suspended partner:(%s)") % self.partner_to_suspend.name,
            body=_("Partner %s suspended from: %s to: %s, by the user %s, for the reason: %s")
            % (
                self.partner_to_suspend.name,
                fields.Date.today().strftime("%d/%m/%y"),
                self.end_date_suspend.strftime("%d/%m/%y"),
                self.env.user.name,
                self.reason,
            ),
        )
        if self.partner_to_suspend.type == "contact" and self.partner_to_suspend.parent_id:
            self.partner_to_suspend.parent_id.message_post(
                subject=_("Suspended family charge:(%s)") % self.partner_to_suspend.name,
                body=_(
                    "Family charge: %s suspended from: %s to: %s, by the user %s, for the reason: %s"
                )
                % (
                    self.partner_to_suspend.name,
                    fields.Date.today().strftime("%d/%m/%y"),
                    self.end_date_suspend.strftime("%d/%m/%y"),
                    self.env.user.name,
                    self.reason,
                ),
            )
