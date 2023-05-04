from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class IotDeviceInherit(models.Model):
    _inherit = "iot.device"

    serial_machine = fields.Char(string="Serial of fiscal machine", default=False)
    max_amount_int = fields.Integer(compute="_compute_max_amounts")
    max_amount_decimal = fields.Integer(compute="_compute_max_amounts")
    max_qty_int = fields.Integer(string="Max quantity int", compute="_compute_max_amounts")
    max_qty_decimal = fields.Integer(string="Max quantity Deciamal", compute="_compute_max_amounts")
    max_payment_amount_int = fields.Integer(compute="_compute_max_amounts")
    max_payment_amount_decimal = fields.Integer(compute="_compute_max_amounts")
    max_description = fields.Integer(default=127)
    flag_21 = fields.Selection([("30", "30")], default="30")
    payment_methods = fields.Selection(
        [
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
            ("8", "8"),
            ("9", "9"),
            ("10", "10"),
            ("11", "11"),
            ("12", "12"),
            ("13", "13"),
            ("14", "14"),
            ("15", "15"),
            ("16", "16"),
            ("17", "17"),
            ("18", "18"),
            ("19", "19"),
            ("20", "20 (*)"),
            ("21", "21 (*)"),
            ("22", "22 (*)"),
            ("23", "23 (*)"),
            ("24", "24 (*)"),
        ]
    )
    payment_method_name = fields.Char()
    command = fields.Char()

    def get_data_to_payment_method(self):
        if not self.payment_method_name or self.payment_method_name == "":
            raise ValidationError(_("Payment method name is empty"))

        if not self.payment_methods:
            raise ValidationError(_("Payment method id is empty"))

        return {
            "payment_method_name": self.payment_method_name,
            "payment_methods": self.payment_methods,
        }

    def get_command(self):
        if not self.command:
            raise ValidationError(_("The command is empty"))

        return {
            "command": self.command,
        }

    @api.depends("flag_21")
    def _compute_max_amounts(self):
        for record in self:
            if record.flag_21 == "30":
                record.max_amount_int = 14
                record.max_amount_decimal = 2
                record.max_qty_int = 14
                record.max_qty_decimal = 3
                record.max_payment_amount_int = 15
                record.max_payment_amount_decimal = 2

    def set_serial_machine(self, res):
        """
        set serial of fiscal machine
        --------
        Exceptions if fiscal machine is not connected
        """
        _logger.info("set_serial_machine %s", res)
        self.write(
            {
                "serial_machine": res["data"]["_registeredMachineNumber"],
                "name": f"{res['data']['_registeredMachineNumber']} - Fiscal Printer HKA",
            }
        )
