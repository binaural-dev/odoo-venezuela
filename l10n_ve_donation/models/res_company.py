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
    donation_income_account_ids = fields.Many2many(
        "account.account",
        relation="res_company_donation_income_account_rel",
        column1="company_id",
        column2="account_id",
        check_company=True,
        string="Received Donations Accounts",
        readonly=False,
        domain=[
            ("account_type", "=", "income"),
        ],
        help="Income accounts that identify the journal entries of the donations "
        "RECEIVED by the company, as opposed to the donations given (which use the "
        "Donation Account). Several accounts are allowed (e.g. events, collection "
        "boxes). Without accounts, no entry is a received donation.",
    )
