from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    is_igtf = fields.Boolean("IGTF active")
    customer_account_igtf_id = fields.Many2one(
        "account.account", domain=[("account_type", "=", "liability_current")]
    )
    supplier_account_igtf_id = fields.Many2one(
        "account.account", domain=[("account_type", "=", "expense")]
    )
    igtf_two_percentage_account = fields.Many2one("account.account")
    igtf_account_expense = fields.Many2one(
        "account.account", domain=[("account_type", "=", "expense")]
    )
    igtf_percentage = fields.Float(string="IGTF Percentage", default=3.00)
    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
        store=True,
    )
    journal_igtf_expense = fields.Many2one("account.journal", string="Journal IGTF Expense")

    show_igtf_suggested_account_move = fields.Boolean(default=False)
    show_igtf_suggested_sale_order = fields.Boolean(default=False)
