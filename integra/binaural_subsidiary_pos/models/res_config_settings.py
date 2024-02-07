from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"


    pos_sh_analytic_account = fields.Many2one(string="Subsidiary")
