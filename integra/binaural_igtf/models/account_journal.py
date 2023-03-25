from odoo import api, models, fields, _
import logging

_logging = logging.getLogger(__name__)

class AccountJournalIgtf(models.Model):
    _inherit = "account.journal"
    def default_is_igtf(self):
        return self.env.company.module_binaural_base_igtf or False
    
    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)

    def _create_payments(self):
        _logging.warning("CREATE PAYMENTS")
        res = super()._create_payments()
        _logging.warning("PAYMEEENTSSSSSSSSSSSS: %s", res)
        return res
    
    def action_create_payments(self):
        _logging.warning("ACTION CREATE PAYMENTS")
        res = super().action_create_payments()
        _logging.warning("RESSSSSSSSSS: %s", res)
        return res