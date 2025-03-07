from odoo import api, models, fields, _
from odoo.tools.sql import column_exists, create_column

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)
