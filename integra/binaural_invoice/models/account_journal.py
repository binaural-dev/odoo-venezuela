from odoo import api, fields, models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    fiscal = fields.Boolean(
        help="If the journal is fiscal",
        default=False,
    )