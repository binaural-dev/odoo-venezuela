from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    donation_account_id = fields.Many2one(
        "account.account", "Donation Account", related="company_id.donation_account_id", readonly=False
    )
