from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"


    is_igtf = fields.Boolean(
        related='company_id.is_igtf',
        readonly=False
    )

    account_igtf_id = fields.Many2one(
        "account.account",
        string="IGTF Account",
        related="company_id.account_igtf_id",
        readonly=False,
    )
    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        related="company_id.igtf_percentage",
        readonly=False,
    )
