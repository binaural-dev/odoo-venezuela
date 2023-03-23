from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    account_igtf = fields.Many2one(
        "account.account",
        string="IGTF Account",
        related="company_id.account_igtf",
        readonly=False,
    )
    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        related="company_id.igtf_percentage",
        readonly=False,
    )
