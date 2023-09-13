
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    check_advance_stock = fields.Boolean(related='company_id.check_advance_stock', readonly=False)