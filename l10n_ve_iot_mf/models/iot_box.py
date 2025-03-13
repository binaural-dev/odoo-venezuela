from odoo import models, fields, api, _


class IotBox(models.Model):
    _inherit = "iot.box"

    ip_public = fields.Char(string="Public IP Address", default=False)
    has_fiscal_machine = fields.Boolean()
    fiscal_port_ids = fields.Many2many("iot.port", "iot_box_ids")
    blacklist = fields.Boolean()
    blacklist_port_ids = fields.Many2many("iot.port", "iot_box_blacklist_ids")


class SerialPort(models.Model):
    _name = "iot.port"

    name = fields.Char(string="Fiscal Ports")
    iot_box_ids = fields.Many2many("iot.box", "fiscal_port_ids")
    iot_box_blacklist_ids = fields.Many2many("iot.box", "blacklist_port_ids")

