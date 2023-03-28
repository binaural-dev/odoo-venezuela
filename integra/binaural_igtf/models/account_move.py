from odoo import api, fields, models, _
from odoo.exceptions import UserError
from contextlib import ExitStack, contextmanager


class AccountMoveIgtf(models.Model):
    _inherit = "account.move"

    def default_is_igtf(self):
        return self.env.company.module_binaural_base_igtf or False
    
    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    # def _get_unbalanced_moves(self, container):
    #    pass

   