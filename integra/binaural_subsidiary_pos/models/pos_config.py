from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    sh_analytic_account = fields.Many2one(
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
    )
