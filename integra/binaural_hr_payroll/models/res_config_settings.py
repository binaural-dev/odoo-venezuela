from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    compute_payroll_using = fields.Selection(
        related="company_id.compute_payroll_using", readonly=False
    )
