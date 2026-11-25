from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    donation_account_id = fields.Many2one(
        "account.account", "In-Kind Donation Expense Account",
        related="company_id.donation_account_id", readonly=False
    )
    donation_expense_account_ids = fields.Many2many(
        "account.account",
        string="Donation Expense Accounts",
        related="company_id.donation_expense_account_ids",
        check_company=True,
        readonly=False,
    )
    donation_income_account_ids = fields.Many2many(
        "account.account",
        string="Received Donations Accounts",
        related="company_id.donation_income_account_ids",
        check_company=True,
        readonly=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """The fields of the company are written one by one: the default
        account is checked against the list of donation expense accounts once
        they are all written, so that the order does not matter."""
        records = super(ResConfigSettings, self.with_context(donation_defer_account_check=True)).create(vals_list)
        records.company_id.with_context(
            donation_defer_account_check=False
        )._check_donation_account_is_an_expense_account()
        return records

    def write(self, vals):
        records = super(ResConfigSettings, self.with_context(donation_defer_account_check=True)).write(vals)
        self.company_id._check_donation_account_is_an_expense_account()
        return records
