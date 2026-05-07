from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    donation_account_id = fields.Many2one(
        "account.account", "Donation Account", related="company_id.donation_account_id", readonly=False
    )
    account_stock_journal_id = fields.Many2one(
        "account.journal", "Stock Journal", related="company_id.account_stock_journal_id", readonly=False
    )
