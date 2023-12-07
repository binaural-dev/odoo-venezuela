from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    sh_analytic_account = fields.Many2one(string="Subsidiary")
