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
