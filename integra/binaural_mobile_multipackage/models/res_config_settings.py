import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_multiple_packaging = fields.Boolean(
        related="company_id.use_multiple_packaging",
        readonly=False,
    )
