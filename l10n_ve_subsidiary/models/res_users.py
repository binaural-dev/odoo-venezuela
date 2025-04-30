import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = "res.users"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Default Subsidiary",
        domain=[("is_subsidiary", "=", True)],
    )

    subsidiary_ids = fields.Many2many(
        "account.analytic.account",
        string="Subsidiaries",
        domain=[("is_subsidiary", "=", True)],
    )

    is_required_subsidiary = fields.Boolean(
        compute="_compute_is_required_subsidiary", store=True
    )

    @api.depends("company_ids.subsidiary", "company_id.subsidiary")
    def _compute_is_required_subsidiary(self):
        for record in self:
            subsidiary_values = record.company_ids.mapped("subsidiary")

            some_has_subsidiary = any(x == True for x in subsidiary_values)

            record.is_required_subsidiary = some_has_subsidiary

    def _assign_default_required_subsidiary_to_user(self):
        self.ensure_one()

        default_subsidiary_id = self.env.ref(
            "l10n_ve_subsidiary.analytic_main_subsidiary"
        )

        self.write(
            {
                "subsidiary_ids": [default_subsidiary_id.id],
                "subsidiary_id": default_subsidiary_id.id,
            }
        )

    def _get_vals_on_base_admin_user_subsidiary_ids(self, vals):
        base_admin_user = self.env.ref("base.user_admin")
        subsidiary_ids = self.env["account.analytic.account"].search(
            [("is_subsidiary", "=", True)]
        )

        for user in self:
            if user.id == base_admin_user.id:
                vals["subsidiary_ids"] = [[6, False, subsidiary_ids.ids]]
                break

        return vals

    @api.constrains("subsidiary_id", "subsidiary_ids", "active")
    def _check_subsidiary(self):
        for user in self.filtered(lambda u: u.active):
            # If the user does not have subsidiaries we do not raise the validation
            if not user.is_required_subsidiary or not (
                user.subsidiary_id and user.subsidiary_ids
            ):
                continue

            if user.subsidiary_id not in user.subsidiary_ids:
                raise ValidationError(
                    _(
                        "Subsidiary %(subsidiary_name)s is not in the allowed "
                        "subsidiaries for user %(user_name)s (%(subsidiary_allowed)s).",
                        subsidiary_name=user.subsidiary_id.name,
                        user_name=user.name,
                        subsidiary_allowed=", ".join(
                            user.mapped("subsidiary_ids.name")
                        ),
                    )
                )

    def write(self, vals):
        vals = self._get_vals_on_base_admin_user_subsidiary_ids(vals)

        res = super().write(vals)

        return res

    def _create_user_from_template(self, values):
        if not self.env.company.subsidiary:
            return super()._create_user_from_template(values)

        values["subsidiary_id"] = self.env.ref(
            "l10n_ve_subsidiary.analytic_main_subsidiary"
        ).id
        values["subsidiary_ids"] = [
            self.env.ref("l10n_ve_subsidiary.analytic_main_subsidiary").id
        ]

        return super()._create_user_from_template(values)
