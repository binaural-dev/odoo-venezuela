from odoo import models, fields, api, _
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR

class PosSession(models.Model):
    _inherit = "pos.session"
    
    def _get_other_related_moves(self):
        if self.env.user.has_group('binaural_fiscal_inspector.group_fiscal_inspectorate_editable'):
            self = self.sudo()
            return super()._get_other_related_moves()
        return super()._get_other_related_moves()