from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def is_user_authorized(self):
        if self.company_id.pos_require_supervisor_key:
            return True
    
        return super().is_user_authorized()