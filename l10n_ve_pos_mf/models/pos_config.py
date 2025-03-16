from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class PosConfigInherit(models.Model):
    _inherit = "pos.config"

    iface_fiscal_data_module = fields.Many2one(
        "iot.device",
        domain=(
            "[('type', '=', 'fiscal_data_module'), '|', ('company_id', '=', False),"
            "('company_id', '=', company_id)]"
        ),
    )
    serial_machine = fields.Char(related="iface_fiscal_data_module.serial_machine")
    flag_21 = fields.Selection(related="iface_fiscal_data_module.flag_21")
    traditional_line = fields.Boolean(related="iface_fiscal_data_module.traditional_line")
    has_cashbox = fields.Boolean(related="iface_fiscal_data_module.has_cashbox")
    access_button_mf = fields.Boolean()
    message_in_head = fields.Boolean()

    def _compute_iot_device_ids(self):
        super()._compute_iot_device_ids()
        for config in self:
            if config.is_posbox:
                config.iot_device_ids += config.iface_fiscal_data_module

    def open_ui(self):
        if not self.is_posbox or not self.iface_fiscal_data_module:
            raise UserError(_("Need activate iot in the Box and use Fiscal Machine"))
        return super().open_ui()
