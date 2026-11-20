from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = "res.company"

    donation_account_id = fields.Many2one(
        "account.account",
        check_company=True,
        string="In-Kind Donation Expense Account",
        readonly=False,
        domain=[
            ("account_type", "=", "expense"),
        ],
        help="Default expense account of the donations in kind: it is proposed as the "
        "valuation account of the Inventory Loss locations of the donation warehouse and "
        "it is the one of the credit note of a donation sale. When there are donation "
        "expense accounts, it must be one of them.",
    )
    donation_expense_account_ids = fields.Many2many(
        "account.account",
        relation="res_company_donation_expense_account_rel",
        column1="company_id",
        column2="account_id",
        check_company=True,
        string="Donation Expense Accounts",
        readonly=False,
        domain=[
            ("account_type", "=", "expense"),
        ],
        help="Expense accounts that a donation given can use, in money and in kind (e.g. "
        "deductible and not deductible). A donation entry in money must have a line on "
        "one of them, and the destination location of a donation delivery must have one "
        "of them as valuation account. Without accounts there is no restriction.",
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
        "donation expense accounts). Several accounts are allowed (e.g. events, collection "
        "boxes). Without accounts, no entry is a received donation.",
    )

    @api.constrains("donation_account_id", "donation_expense_account_ids")
    def _check_donation_account_is_an_expense_account(self):
        # Saving the settings writes each field apart, in no fixed order: the
        # settings check it once, when all of them are written.
        if self.env.context.get("donation_defer_account_check"):
            return
        for company in self:
            accounts = company.donation_expense_account_ids
            if accounts and company.donation_account_id and company.donation_account_id not in accounts:
                raise ValidationError(_(
                    "The In-Kind Donation Expense Account %(account)s must be one of the "
                    "Donation Expense Accounts of %(company)s.",
                    account=company.donation_account_id.display_name,
                    company=company.display_name,
                ))

    def write(self, vals):
        """The direction of a donation entry (received or given) is told by
        these accounts when its document is printed, so they cannot change
        while a posted donation entry uses one of the accounts that is added
        or removed: its document would silently switch between the Donation
        Certificate and the Donation Receipt."""
        if "donation_income_account_ids" not in vals:
            return super().write(vals)
        before = {company.id: company.donation_income_account_ids for company in self}
        res = super().write(vals)
        Move = self.env["account.move"].sudo()
        for company in self:
            after = company.donation_income_account_ids
            changed = (before[company.id] | after) - (before[company.id] & after)
            if not changed:
                continue
            moves = Move.search([
                ("company_id", "=", company.id),
                ("move_type", "=", "entry"),
                ("is_donation", "=", True),
                ("state", "=", "posted"),
                ("line_ids.account_id", "in", changed.ids),
            ])
            if moves:
                raise ValidationError(_(
                    "The received donations accounts of %(company)s cannot change: %(count)s "
                    "posted donation entries use %(accounts)s, and the document of an entry "
                    "(Donation Certificate or Donation Receipt) depends on these accounts.",
                    company=company.display_name,
                    count=len(moves),
                    accounts=", ".join(changed.mapped("display_name")),
                ))
        return res
