
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    check_advance_stock = fields.Boolean(related='company_id.check_advance_stock', readonly=False)
    use_fee_percentage = fields.Boolean(related='company_id.use_fee_percentage', readonly=False)
    apply_fob = fields.Boolean(related='company_id.apply_fob', readonly=False)
    apply_cif = fields.Boolean(related='company_id.apply_cif', readonly=False)
    service_products_ids = fields.Many2many(related='company_id.service_products_ids', readonly=False)
    