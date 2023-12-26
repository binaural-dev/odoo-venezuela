from odoo import api, fields, models


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
