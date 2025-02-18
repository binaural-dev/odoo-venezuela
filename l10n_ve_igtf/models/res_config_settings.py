from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_igtf = fields.Boolean(related="company_id.is_igtf", readonly=False)

    customer_account_igtf_id = fields.Many2one(
        "account.account",
        string="Customer IGTF Account",
        related="company_id.customer_account_igtf_id",
        readonly=False,
    )

    supplier_account_igtf_id = fields.Many2one(
        "account.account",
        string="Supplier IGTF Account",
        related="company_id.supplier_account_igtf_id",
        readonly=False,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        related="company_id.igtf_percentage",
        readonly=False,
    )
    igtf_two_percentage_account = fields.Many2one(
        "account.account",
        string="IGTF Two Percentage Account",
        related="company_id.igtf_two_percentage_account",
        readonly=False,
    )

    igtf_account_expense = fields.Many2one(
        "account.account",
        string="IGTF Account Expense",
        related="company_id.igtf_account_expense",
        readonly=False,
    )

    journal_igtf_expense = fields.Many2one(
        "account.journal",
        string="Journal IGTF Expense",
        related="company_id.journal_igtf_expense",
        readonly=False,
    )

    show_igtf_suggested_account_move = fields.Boolean(
        related="company_id.show_igtf_suggested_account_move", readonly=False
    )
    show_igtf_suggested_sale_order = fields.Boolean(
        related="company_id.show_igtf_suggested_sale_order", readonly=False
    )
