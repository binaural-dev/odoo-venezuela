from odoo import fields, models, api, _


class ResConfigSetting(models.TransientModel):
    _inherit = "res.config.settings"

    ref_required = fields.Boolean(related="company_id.ref_required", readonly=False)
