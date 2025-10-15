from odoo import models, fields, api, _


class IotBox(models.Model):
    _inherit = "iot.box"

    ip_public = fields.Char(string="Public IP Address", default=False)
    has_fiscal_machine = fields.Boolean()
    has_pinpad_machine = fields.Boolean()
    fiscal_port_ids = fields.Many2many("iot.port", "iot_box_ids")
    pinpad_port_id = fields.Many2one("iot.port", string="Pinpad Port")
    blacklist = fields.Boolean()
    blacklist_port_ids = fields.Many2many("iot.port", "iot_box_blacklist_ids")

    @api.onchange("has_pinpad_machine")
    def _onchange_has_pinpad_machine(self):
        """ Clear pinpad port if field 'has_pinpad_machine' is unchecked """
        for record in self:
            if not record.has_pinpad_machine:
                record.pinpad_port_id = False

class SerialPort(models.Model):
    _name = "iot.port"

    name = fields.Char(string="Fiscal Ports")
    iot_box_ids = fields.Many2many("iot.box", "fiscal_port_ids")
    iot_box_blacklist_ids = fields.Many2many("iot.box", "blacklist_port_ids")

