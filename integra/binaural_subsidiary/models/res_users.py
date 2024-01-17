from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Default Subsidiary",
        domain=[("is_subsidiary", "=", True)],
    )
    subsidiary_ids = fields.Many2many(
        "account.analytic.account", string="Subsidiaries", domain=[("is_subsidiary", "=", True)]
    )

    @api.constrains("subsidiary_id", "subsidiary_ids", "active")
    def _check_subsidiary(self):
        for user in self.filtered(lambda u: u.active):
            if user.subsidiary_id not in user.subsidiary_ids:
                raise ValidationError(
                    _(
                        "Subsidiary %(subsidiary_name)s is not in the allowed subsidiaries for user %(user_name)s (%(subsidiary_allowed)s).",
                        subsidiary_name=user.subsidiary_id.name,
                        user_name=user.name,
                        subsidiary_allowed=", ".join(user.mapped("subsidiary_ids.name")),
                    )
                )
