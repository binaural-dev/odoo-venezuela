from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    custom_manifest = fields.Text(related="company_id.custom_manifest", readonly=False)

    assetlink = fields.Text(related="company_id.assetlink", readonly=False)
    