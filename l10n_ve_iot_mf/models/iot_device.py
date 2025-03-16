from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

import logging

_logger = logging.getLogger(__name__)


class IotDeviceInherit(models.Model):
    _inherit = "iot.device"

    manufacturer_type = fields.Selection(
        selection=[("HKA", "The Factory HKA"), ("PnP", "PnP Desarrollos")],
        string="Manufacturer Type",
        compute="_compute_manufacturer_type",
    )
    serial_machine = fields.Char(string="Serial of fiscal machine", default=False)
    max_amount_int = fields.Integer(compute="_compute_max_amounts")  # deprecated
    max_amount_decimal = fields.Integer(compute="_compute_max_amounts")  # deprecated
    max_qty_int = fields.Integer(
        string="Max quantity int", compute="_compute_max_amounts"
    )  # deprecated
    max_qty_decimal = fields.Integer(
        string="Max quantity Deciamal", compute="_compute_max_amounts"
    )  # deprecated
    max_payment_amount_int = fields.Integer(compute="_compute_max_amounts")  # deprecated
    max_payment_amount_decimal = fields.Integer(compute="_compute_max_amounts")  # deprecated
    max_description = fields.Integer(default=127)  # deprecated
    traditional_line = fields.Boolean(default=True)
    flag_21 = fields.Selection(
        [("30", "30"), ("00", "00"), ("01", "01"), ("02", "02")], default="00"
    )
    flag_24 = fields.Selection([("00", "00"), ("01", "01")], default="00")
    show_version = fields.Boolean()
    has_cashbox = fields.Boolean()
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
    reprint_range_from_number = fields.Char()
    reprint_range_to_number = fields.Char()
    reprint_range_from_date = fields.Date(default=fields.Date().today())
    reprint_range_to_date = fields.Date(default=fields.Date().today())
    reprint_type = fields.Selection([("date", "Date"), ("number", "Number")])
    reprint_type_number = fields.Selection(
        [
            ("RF", "Invoices"),
            ("RC", "Refund"),
            ("RT", "No Fiscal"),
            ("RX", "Report X"),
            ("RZ", "Report Z"),
            ("R@", "All"),
        ],
        default="RF",
    )

    reprint_type_date = fields.Selection(
        [
            ("Rf", "Invoices"),
            ("Rc", "Refund"),
            ("Rt", "No Fiscal"),
            ("Rx", "Report X"),
            ("Rz", "Report Z"),
            ("Ra", "All"),
        ],
        default="Rf",
    )

    resume_range_from = fields.Date(default=fields.Date().today())
    resume_range_to = fields.Date(default=fields.Date().today())


    def _compute_manufacturer_type(self):
        for record in self:
            if record.name.__contains__("HKA"):
                record.manufacturer_type = "HKA"
                continue
            if record.name.__contains__("PnP"):
                record.manufacturer_type = "PnP"
                continue
            record.manufacturer_type = False

    def configure_device(self):
        return {
            "flag_21": self.flag_21,
            "flag_24": self.flag_24,
            "show_version": "77" if self.show_version else "00",
        }

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

    def get_range_resume(self):
        if not self.resume_range_from or not self.resume_range_to:
            raise ValidationError(_("You must fill in the start or end field, if there is one"))
        if self.resume_range_to < self.resume_range_from:
            raise ValidationError(_("Range to is greater than range from"))

        return {
            "resume_range_from": self.resume_range_from.strftime("%d%m%y"),
            "resume_range_to": self.resume_range_to.strftime("%d%m%y"),
        }

    def get_range_reprint(self):
        if self.reprint_type == "number" and (
            not self.reprint_range_from_number or not self.reprint_range_to_number
        ):
            raise ValidationError(
                _("You must fill in the start or end field, if there is one, repeat the number")
            )

        if self.reprint_type == "date" and (
            not self.reprint_range_from_date or not self.reprint_range_to_date
        ):
            raise ValidationError(
                _("You must fill in the start or end field, if there is one, repeat the date")
            )

        if self.reprint_type == "number" and int(self.reprint_range_to_number) < int(
            self.reprint_range_from_number
        ):
            raise ValidationError(_("Range to is greater than range from"))

        if (
            self.reprint_type == "date"
            and self.reprint_range_to_date < self.reprint_range_from_date
        ):
            raise ValidationError(_("Range to is greater than range from"))

        if self.reprint_type == "number":
            data = {
                "reprint_range_from": self.reprint_range_from_number,
                "reprint_range_to": self.reprint_range_to_number,
                "mode": self.reprint_type_number,
            }
        else:
            data = {
                "reprint_range_from": self.reprint_range_from_date.strftime("%d%m%y"),
                "reprint_range_to": self.reprint_range_to_date.strftime("%d%m%y"),
                "mode": self.reprint_type_date,
            }

        return data

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
