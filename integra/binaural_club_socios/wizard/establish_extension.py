from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class EstablishExtension(models.Model):
    _name = "establish.extension"

    reason = fields.Text(string="Reason")

    new_end_date = fields.Date(string="New end date")

    partner_to_establish = fields.Many2one("res.partner", string="Partner to Stablish")

    def establish_extension(self):
        if not self.reason:
            raise UserError("Required Reason")
        if not self.new_end_date:
            raise UserError("Required new end date")
        if self.new_end_date <= fields.Date.today():
            raise UserError("The final date of suspension must be greater than the current date.")
        if not self.partner_to_establish:
            raise UserError("Partner to establish extension is mandatory.")
        self.partner_to_establish.write({"end_date_partner": self.new_end_date})
        self.partner_to_establish.message_post(
            subject=_("Establish extension:(%s)") % self.partner_to_establish.name,
            body=_(
                "Extension established for %s, new member end date: %s, by user  %s, for the reason: %s"
            )
            % (
                self.partner_to_establish.name,
                self.new_end_date.strftime("%d/%m/%y"),
                self.env.user.name,
                self.reason,
            ),
        )
        for child in self.partner_to_establish.child_ids:
            child.end_date_partner = self.new_end_date
