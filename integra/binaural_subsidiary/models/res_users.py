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
        domain=[("is_subsidiary", "=", True)]
    )

    is_required_subsidiary = fields.Boolean(
        compute="_compute_is_required_subsidiary",
        store=True
    )

    @api.depends('company_ids.subsidiary', 'company_id.subsidiary')
    def _compute_is_required_subsidiary(self):
        for record in self:
            subsidiary_values = record.company_ids.mapped('subsidiary')

            some_has_subsidiary = any(x == True for x in subsidiary_values)

            record.is_required_subsidiary = some_has_subsidiary

    def _get_vals_on_base_admin_user_subsidiary_ids(self, vals):
        base_admin_user = self.env.ref('base.user_admin')
        subsidiary_ids = self.env["account.analytic.account"].search([("is_subsidiary", "=", True)])
        
        if self.id == base_admin_user.id:
            vals['subsidiary_ids'] = [[6, False, subsidiary_ids.ids]]

        return vals

    @api.constrains("subsidiary_id", "subsidiary_ids", "active")
    def _check_subsidiary(self):
        for user in self.filtered(lambda u: u.active):
            
            if not user.is_required_subsidiary:
                continue

            if user.subsidiary_id not in user.subsidiary_ids:
                raise ValidationError(
                    _(
                        "Subsidiary %(subsidiary_name)s is not in the allowed subsidiaries for user %(user_name)s (%(subsidiary_allowed)s).",
                        subsidiary_name=user.subsidiary_id.name,
                        user_name=user.name,
                        subsidiary_allowed=", ".join(user.mapped("subsidiary_ids.name")),
                    )
                )

    def write(self, vals):
        vals = self._get_vals_on_base_admin_user_subsidiary_ids(vals)

        res = super().write(vals)

        return res