import traceback
from collections import namedtuple

from odoo import _
from odoo.addons.hw_drivers.event_manager import event_manager
from odoo.addons.hw_drivers.iot_handlers.drivers.SerialBaseDriver import (
    SerialDriver,
    serial_connection,
)

import logging

_logger = logging.getLogger(__name__)

SerialProtocol = namedtuple(
    "SerialProtocol",
    "name baudrate bytesize stopbits parity timeout writeTimeout commandDelay measureDelay",
)


class SerialBaseFiscalDriver(SerialDriver):
    connection_type = "serial"

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self.device_type = "fiscal_data_module"
        self.device_connection = "serial"

    def _set_actions(self):
        self._actions.update(
            {
                "serial_machine": self.serial_machine,
                "report_x": self.print_report_x,
                "report_z": self.print_report_z,
                "print_out_invoice": self.print_out_invoice,
                "print_out_refund": self.print_out_refund,
                "test": self.test,
            }
        )

    def run(self):
        self._status["status"] = self.STATUS_CONNECTED
        self._push_status()

    def test(self, data):
        self._test()
        self.data["value"] = {"valid": True, "message": "TEST"}
        event_manager.device_changed(self)

    def serial_machine(self, data):
        self.data["value"] = self._get_serial_machine(data)
        event_manager.device_changed(self)

    def print_report_x(self, data):
        self.data["value"] = self._print_report_x()
        event_manager.device_changed(self)

    def print_report_z(self, data):
        self.data["value"] = self._print_report_z()
        event_manager.device_changed(self)

    def print_out_invoice(self, invoice):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _invoice = invoice.get("data", False)
        if _invoice:
            invoice = _invoice
        _logger.warning("print_out_invoice: %s" % invoice)
        valid, _msg = self._validate_invoice_parameter(invoice)
        msg = ""

        if not valid or len(_msg) > 0:
            msg = ", ".join(_msg)
            self.data["value"] = {"valid": valid, "message": msg}
            event_manager.device_changed(self)
            return self.data["value"]
        self.data["value"] = self._print_invoice(invoice, "out_invoice")
        event_manager.device_changed(self)
        return self.data["value"]

    def print_out_refund(self, invoice):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _invoice = invoice.get("data", False)
        if _invoice:
            invoice = _invoice
        valid, _msg = self._validate_out_refund_parameter(invoice)
        msg = ""

        if not valid or len(_msg) > 0:
            msg = ", ".join(_msg)
            self.data["value"] = {"valid": valid, "message": msg}
            event_manager.device_changed(self)
            return self.data["value"]

        self.data["value"] = self._print_invoice(invoice, "out_refund")
        event_manager.device_changed(self)
        return self.data["value"]

    # -------------------------
    # TODO: Validations
    # --------------------------

    def _validate_invoice_parameter(self, invoice):
        msg = []
        valid = True

        if not invoice:
            msg.append("No se recibio informacion de la factura")
            return False, msg

        invoice_keys = invoice.keys()

        if not "company_id" in invoice_keys:
            msg.append("No se encontro la empresa")
            valid = False
        if not "partner_id" in invoice_keys:
            msg.append("No se recibio informacion del cliente")
            return False, msg

        partner = invoice["partner_id"].keys()

        if not "vat" in partner or invoice["partner_id"]["vat"] == "":
            msg.append("El cliente no tiene cedula")
            valid = False
        if not "name" in partner or invoice["partner_id"]["name"] == "":
            msg.append("El cliente no tiene nombre")
            valid = False

        if not "invoice_lines" in invoice_keys or len(invoice["invoice_lines"]) == 0:
            msg.append("No se recibio informacion de los productos")
            valid = False
            return valid, msg

        for line in invoice["invoice_lines"]:
            line_keys = line.keys()
            if not "price_unit" in line_keys:
                msg.append("No se encontro el precio del producto")
                valid = False
            if not "quantity" in line_keys:
                msg.append("No se encontro la cantidad del producto")
                valid = False
            if not "tax" in line_keys or int(line["tax"]) < 0 and int(line["tax"]) > 4:
                msg.append("El impuesto no es valido")
                valid = False
            if not "name" in line_keys:
                msg.append("No se encontro el nombre del producto")
                valid = False

        if not "payment_lines" in invoice_keys or len(invoice["payment_lines"]) == 0:
            msg.append("No se recibio informacion de los pagos")
            valid = False
            return valid, msg

        for line in invoice["payment_lines"]:
            line_keys = line.keys()
            if not "amount" in line_keys:
                msg.append("No se recibio el monto del pago")
                valid = False
            if (
                not "payment_method" in line_keys
                or int(line["payment_method"]) < 1
                and int(line["payment_method"]) > 24
            ):
                msg.append("El metodo de pago no es aceptado o no se recibio")
                valid = False

        return valid, msg

    def _validate_out_refund_parameter(self, invoice):
        msg = []
        valid = True

        if not invoice:
            msg.append("No se recibio informacion de la nota de credito")
            return False, msg

        invoice_keys = invoice.keys()

        if not "company_id" in invoice_keys:
            msg.append("No se encontro la empresa")
            valid = False
        if not "partner_id" in invoice_keys:
            msg.append("No se recibio informacion del cliente")
            return False, msg
        if not "invoice_affected" in invoice_keys:
            msg.append("No se recibio informacion de la factura afectada")
            return False, msg

        partner = invoice["partner_id"].keys()

        if not "vat" in partner or invoice["partner_id"]["vat"] == "":
            msg.append("El cliente no tiene cedula")
            valid = False
        if not "name" in partner or invoice["partner_id"]["name"] == "":
            msg.append("El cliente no tiene nombre")
            valid = False

        invoice_affected = invoice["invoice_affected"].keys()
        if not "number" in invoice_affected or invoice["invoice_affected"]["number"] == "":
            msg.append("No se recibio una factura afectada")
            valid = False
        if (
            not "serial_machine" in invoice_affected
            or invoice["invoice_affected"]["serial_machine"] == ""
        ):
            msg.append("No se recibio el serial de la maquina fiscal")
            valid = False
        if not "date" in invoice_affected or invoice["invoice_affected"]["date"] == "":
            msg.append("No se recibio la fecha de la factura afectada")
            valid = False

        if not "invoice_lines" in invoice_keys or len(invoice["invoice_lines"]) == 0:
            msg.append("No se recibio informacion de los productos")
            valid = False
            return valid, msg

        for line in invoice["invoice_lines"]:
            line_keys = line.keys()
            if not "price_unit" in line_keys:
                msg.append("No se encontro el precio del producto")
                valid = False
            if not "quantity" in line_keys:
                msg.append("No se encontro la cantidad del producto")
                valid = False
            if not "tax" in line_keys or int(line["tax"]) < 0 and int(line["tax"]) > 4:
                msg.append("El impuesto no es valido")
                valid = False
            if not "name" in line_keys:
                msg.append("No se encontro el nombre del producto")
                valid = False

        if not "payment_lines" in invoice_keys or len(invoice["payment_lines"]) == 0:
            msg.append("No se recibio informacion de los pagos")
            valid = False
            return valid, msg

        for line in invoice["payment_lines"]:
            line_keys = line.keys()
            if not "amount" in line_keys:
                msg.append("No se recibio el monto del pago")
                valid = False
            if (
                not "payment_method" in line_keys
                or int(line["payment_method"]) < 1
                and int(line["payment_method"]) > 24
            ):
                msg.append("El metodo de pago no es aceptado o no se recibio")
                valid = False

        return valid, msg

    # -------------------------
    # TODO: Implementations
    # --------------------------

    def _test(self):
        return {"valid": False, "message": "No se ha implementado"}

    def _print_invoice(self, invoice, move_type):
        return {"valid": False, "message": "No se ha implementado"}

    def _print_report_x(self) :
        return {"valid": False, "message": "No se ha implementado"}

    def _print_report_z(self) :
        return {"valid": False, "message": "No se ha implementado"}

    def _get_serial_machine(self, data):
        return {"valid": False, "message": "No se ha implementado"}
