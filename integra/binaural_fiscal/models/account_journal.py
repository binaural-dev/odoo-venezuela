from odoo import fields, models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    fiscal = fields.Boolean(
        help="If the journal is fiscal",
        default=False,
        tracking=True,
    )
