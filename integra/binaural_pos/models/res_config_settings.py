from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_binaural_pos_igtf = fields.Boolean(related='company_id.module_binaural_pos_igtf', readonly=False)
    module_binaural_igtf = fields.Boolean(related='company_id.module_binaural_igtf', readonly=False)
