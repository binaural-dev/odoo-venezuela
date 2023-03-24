from odoo import api, models, fields, _

class AccountJournalIgtf(models.Model):
    _inherit = "account.journal"

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)
