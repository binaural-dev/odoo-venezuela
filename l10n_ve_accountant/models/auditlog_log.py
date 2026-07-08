from odoo import models, _
from odoo.exceptions import UserError

class AuditlogLog(models.Model):
    _inherit = 'auditlog.log'

    def unlink(self):
        if not self.env.user.has_group('l10n_ve_accountant.group_fiscal_config_support'):
            raise UserError(_("It is not possible to delete audit records."))        
        return super(AuditlogLog, self).unlink()