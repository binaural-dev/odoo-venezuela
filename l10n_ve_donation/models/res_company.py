from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    donation_account_id = fields.Many2one(
        "account.account",
        check_company=True,
        string="Donation Account",
        readonly=False,
        domain=[
            ("account_type", "=", "expense"),
        ],
    )
    account_stock_journal_id = fields.Many2one(
        "account.journal",
        string="Stock Journal",
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        check_company=True,
        readonly=False,
    )
