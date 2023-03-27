from odoo import api, models, fields, _

class AccountJournalIgtf(models.Model):
    _inherit = "account.journal"
    def default_is_igtf(self):
        return self.env.company.module_binaural_base_igtf or False
    
    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)
