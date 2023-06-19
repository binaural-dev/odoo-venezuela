from odoo import fields, osv, models
from odoo.tools.translate import _
import pdb
#CHANGE WARNING_MODULE with your module name
WARNING_MODULE = 'meli_oerp_multiple'
WARNING_TYPES = [('warning','Warning'),('info','Information'),('error','Error')]

class warning(models.TransientModel):
    _inherit = 'meli.warning'

    def _get_view_id(self ):
        """Get the view id
        @return: view id, or False if no view found
        """
        res = self.env['ir.model.data'].check_object_reference( WARNING_MODULE, 'warning_form')
        return res and res[1] or False
