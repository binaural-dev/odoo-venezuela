import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = "pos.config"

    megasoft_iot_id = fields.Many2one(
        "iot.box",
        string="IoT Device",
        help="When setting a device here, the exchange be printed through this device",
    )
