from odoo import _, fields, models
from odoo.exceptions import ValidationError

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
