from odoo import models

class AuditlogRule(models.Model):
    _inherit = 'auditlog.rule'

    def set_to_draft(self):
        return super(AuditlogRule, self.sudo()).set_to_draft()

    def set_to_confirmed(self):
        return super(AuditlogRule, self.sudo()).set_to_confirmed()