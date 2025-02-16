from odoo import api, models, fields, _
from odoo.tools.sql import column_exists, create_column

class AccountJournalIgtf(models.Model):
    _inherit = "account.journal"

    def default_is_igtf(self):
        return self.env.company.is_igtf or False
    
    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)
