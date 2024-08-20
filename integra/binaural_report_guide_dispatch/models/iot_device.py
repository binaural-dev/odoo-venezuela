from odoo import fields, models


class IoTDevice(models.Model):
    _inherit = "iot.device"

    escpos_limit_char_tipe_a = fields.Integer(default=60)
    escpos_limit_char_tipe_b = fields.Integer(default=96)
