from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    validate_user_creation_by_company = fields.Boolean(
        related='company_id.validate_user_creation_by_company',
        readonly=False
    )

    validate_user_creation_general = fields.Boolean(
        related='company_id.validate_user_creation_general',
        readonly=False
    )
    