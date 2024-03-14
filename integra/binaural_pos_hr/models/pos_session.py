from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def is_user_authorized(self):
        if self.config_id.pos_discount_require_supervisor_key:
            return True
    
        return super().is_user_authorized()