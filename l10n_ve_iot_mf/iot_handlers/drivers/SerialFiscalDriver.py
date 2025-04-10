import os
import logging
import time
import serial
import serial.tools.list_ports
import operator
import datetime
import sys
import json
import glob
import urllib3
import platform
from functools import reduce
import traceback

from odoo.addons.hw_drivers.iot_handlers.sdk.ReportData import ReportData
from odoo.addons.hw_drivers.iot_handlers.sdk.S1PrinterData import S1PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S2PrinterData import S2PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S3PrinterData import S3PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S4PrinterData import S4PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S5PrinterData import S5PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S6PrinterData import S6PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S7PrinterData import S7PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S8EPrinterData import S8EPrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S8PPrinterData import S8PPrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.S25PrinterData import S25PrinterData
from odoo.addons.hw_drivers.iot_handlers.sdk.AcumuladosX import AcumuladosX

from odoo import http, _
from odoo.addons.hw_drivers.main import iot_devices
from odoo.addons.hw_drivers.event_manager import event_manager
from odoo.addons.hw_drivers.tools import helpers

from odoo.addons.hw_drivers.controllers.driver import DriverController

from odoo.addons.hw_drivers.iot_handlers.drivers.SerialBaseDriver import (
    SerialDriver,
    SerialProtocol,
    serial_connection,
)

FLAG_21 = {
    "30": {
        "max_amount_int": 14,
        "max_amount_decimal": 2,
        "max_payment_amount_int": 15,
        "max_payment_amount_decimal": 2,
        "max_qty_int": 14,
        "max_qty_decimal": 3,
        "disc_int": 15,
        "disc_decimal": 2,
    },
    "00": {
        "max_amount_int": 8,
        "max_amount_decimal": 2,
        "max_payment_amount_int": 10,
        "max_payment_amount_decimal": 2,
        "max_qty_int": 5,
        "max_qty_decimal": 3,
        "disc_int": 7,
        "disc_decimal": 2,
    },
    "01": {
        "max_amount_int": 7,
        "max_amount_decimal": 3,
        "max_payment_amount_int": 10,
        "max_payment_amount_decimal": 2,
        "max_qty_int": 5,
        "max_qty_decimal": 3,
        "disc_int": 7,
        "disc_decimal": 2,
    },
    "02": {
        "max_amount_int": 6,
        "max_amount_decimal": 4,
        "max_payment_amount_int": 10,
        "max_payment_amount_decimal": 2,
        "max_qty_int": 5,
        "max_qty_decimal": 3,
        "disc_int": 7,
        "disc_decimal": 2,
    },
}

TAX = {
    "0": " ",
    "1": "!",
    "2": '"',
    "3": "#",
}


class BinauralDriverController(DriverController):
    @http.route(
        "/hw_drivers/event", type="json", auth="none", cors="*", csrf=False, save_session=False
    )
    def event(self, listener):
        """
        listener is a dict in witch there are a sessions_id and a dict of device_identifier to listen
        """
        req = event_manager.add_request(listener)
        # Search for previous events and remove events older than 5 seconds
        oldest_time = time.time() - 5
        for event in list(event_manager.events):
            if event["time"] < oldest_time:
                del event_manager.events[0]
                continue
            if (
                event["device_identifier"] in listener["devices"]
                and event["time"] > listener["last_event"]
            ):
                event["session_id"] = req["session_id"]
                _logger.info("EVENT %s", event)
                return event

        # Wait for new event
        if req["event"].wait(50):
            req["event"].clear()
            req["result"]["session_id"] = req["session_id"]
            _logger.info("EVENT %s", req["result"])
            return req["result"]


_logger = logging.getLogger(__name__)

DEVICE_NAME = "/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0"
DEVICE_SHORT_NAME = "/dev/ttyACM"

FiscalProtocol = SerialProtocol(
    name="FiscalMachine",
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    stopbits=serial.STOPBITS_ONE,
    parity=serial.PARITY_EVEN,
    timeout=1.5,
    writeTimeout=5,
    measureRegexp=None,
    statusRegexp=None,
    commandTerminator=b"",
    commandDelay=0.2,
    measureDelay=0.2,
    newMeasureDelay=0.2,
    measureCommand=b"",
    emptyAnswerValid=False,
)


class SerialFiscalDriver(SerialDriver):
    connection_type = "serial"

    _protocol = FiscalProtocol
    mdepura = False
    ##

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self.identifier = identifier
        self.device_type = "fiscal_data_module"
        self.device_connection = "serial"
        self._connection = None
        self._set_actions()

    @classmethod
    def supported(cls, device):
        try:
            condition = False

            if platform.system() == "Windows":
                server = helpers.get_odoo_server_url()
                urllib3.disable_warnings()
                http = urllib3.PoolManager(cert_reqs="CERT_NONE")
                waiting = http.request(
                    "GET",
                    server + "/iot_fiscal/ports",
                )

                b_body = waiting._body
                body = json.loads(b_body.decode("utf-8"))

                condition = device["identifier"] in body[helpers.get_mac_address()]

            elif platform.system() == "Linux":
                condition = device["identifier"].__contains__(DEVICE_NAME) or device[
                    "identifier"
                ].__contains__(DEVICE_SHORT_NAME)

            if condition:
                try:
                    protocol = cls._protocol
                    return True
                except Exception:
                    _logger.exception(
                        "Error while probing %s with protocol %s" % (device, cls._protocol.name)
                    )
                return True
        except Exception as e:
            _logger.error("Could not reach configured server")
            _logger.error("A error encountered : %s " % e)
            return super().supported(device)
        return super().supported(device)

    def _set_actions(self):
        self._actions.update(
            {
                "status": self.get_status_machine,
                "status1": self.GetS1PrinterData,
                "logger": self.logger,
                "logger_multi": self.logger_multi,
                "programacion": self.programacion,
                "print_out_invoice": self.print_out_invoice,
                "print_out_refund": self.print_out_refund,
                "reprint": self.reprint,
                "reprint_type": self.reprint_type,
                "reprint_date": self.reprint_date,
                "print_resume": self.print_resume,
                "test": self.test,
                "report_x": self.PrintXReport,
                "report_z": self.PrintZReport,
                "get_last_invoice_number": self.get_last_invoice_number,
                "configure_device": self.configure_device,
                # deprecated
                "pre_invoice": self.pre_invoice,
                "hello": self.get_last_invoice_number,
                "print_debit_note": self.print_debit_note
            }
        )

    def run(self):
        self._status["status"] = self.STATUS_CONNECTED
        self._push_status()

    def configure_device(self, data):
        if data["data"].get("flag_21", False):
            self.SendCmd("PJ21" + data["data"]["flag_21"])
        if data["data"].get("flag_24", False):
            self.SendCmd("PJ24" + data["data"]["flag_24"])
        if data["data"].get("show_version", False):
            self.SendCmd("PJ77" + data["data"]["show_version"])
        self.SendCmd("PJ6300")

        payment_methods = [
            "PE01EFECTIVO 01",
            "PE02EFECTIVO 02",
            "PE03PAGO MOVIL 01",
            "PE04PAGO MOVIL 02",
            "PE05PAGO MOVIL 03",
            "PE06PAGO MOVIL 04",
            "PE07TRANSFERENCIA 01 ",
            "PE08TRANSFERENCIA 02",
            "PE09TRANSFERENCIA 03",
            "PE10TRANSFERENCIA 04",
            "PE11PDV 01 ",
            "PE12PDV 02",
            "PE13PDV 03",
            "PE14PDV 04",
            "PE15CREDITO 01",
            "PE16CREDITO 02",
            "PE19DIVISA 02",
            "PE20DIVISA 01",
            "PE21ZELLE",
        ]
        for line in payment_methods:
            self.SendCmd(line)

        self.data["value"] = {"status": "true"}
        event_manager.device_changed(self)

    def _set_name(self):
        """Tries to build the device's name based on its type and protocol name but falls back on a default name if that doesn't work."""
        try:
            with serial_connection(self.device_identifier, self._protocol) as connection:
                self._connection = connection
                trama = self._States("S1")
                trama = self._States("S1")
                res = S1PrinterData(trama)
                machine_number = res.__dict__.get("_registeredMachineNumber", "Prueba")
                name = machine_number + " - Fiscal Printer HKA"
        except Exception as eror:
            _logger.info("ERROR %s", eror)
            name = "Desconocido - Fiscal Printer HKA"
        self.device_name = name

    def test(self, data):
        self.SendCmd("7")
        self.SendCmd("800")
        self.SendCmd("80$Binaural Test")
        self.SendCmd("80!Documento de pruebas")
        self.SendCmd("810")
        self.data["value"] = {"status": "true"}
        event_manager.device_changed(self)

    def logger(self, data):
        self.SendCmd(str(data["data"]))
        _logger.info(data["data"])
        self.data["value"] = {"status": "true"}
        event_manager.device_changed(self)

    def logger_multi(self, data):
        lines = data.get("data", [])
        for line in lines:
            self.SendCmd(str(line))
        self.data["value"] = {"status": "true"}
        event_manager.device_changed(self)

    def print_out_invoice(self, invoice):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _invoice = invoice.get("data", False)
        if _invoice:
            invoice = _invoice
        valid, _msg = self._validate_invoice_parameter(invoice)
        msg = ""

        if not valid or len(_msg) > 0:
            msg = ", ".join(_msg)
            self.data["value"] = {"valid": valid, "message": msg}
            event_manager.device_changed(self)
            return self.data["value"]
        self.data["value"] = self._print_out_invoice(invoice)
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

        self.data["value"] = self._print_out_refund(invoice)
        event_manager.device_changed(self)
        return self.data["value"]

    def print_resume(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        _logger.info(data)
        self.SendCmd("I2S" + str(data["resume_range_from"] + data["resume_range_to"]))
        self.data["value"] = {"valid": True, "message": "MENSAJE"}
        event_manager.device_changed(self)
        return self.data["value"]

    def reprint_date(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        _logger.info(data)
        mode = data.get("mode", "Rs")
        self.SendCmd(
            mode + str(data["reprint_range_from"].zfill(7) + data["reprint_range_to"].zfill(7))
        )
        self.data["value"] = {"valid": True, "message": "MENSAJE"}
        event_manager.device_changed(self)
        return self.data["value"]

    def reprint_type(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        _logger.info(data)
        mode = data.get("mode", "R@")
        self.SendCmd(
            mode + str(data["reprint_range_from"].zfill(7) + str(data["reprint_range_to"].zfill(7)))
        )
        self.data["value"] = {"valid": True, "message": "MENSAJE"}
        event_manager.device_changed(self)
        return self.data["value"]

    def reprint(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        mode = ""
        if data["type"] == "out_invoice":
            mode = "RF"
        if data["type"] == "out_refund":
            mode = "RC"
        if mode == "":
            self.data["value"] = {"valid": False, "message": "Datos no validos"}
            event_manager.device_changed(self)
            return self.data["value"]
        self.SendCmd(
            mode + "0" + str(data["mf_number"].zfill(6) + "0" + str(data["mf_number"].zfill(6)))
        )
        self.data["value"] = {"valid": True, "message": "MENSAJE"}
        event_manager.device_changed(self)
        return self.data["value"]

    def _print_out_refund(self, invoice):
        valid = True
        cmd = []

        max_amount_int = FLAG_21[invoice["flag_21"]]["max_amount_int"]
        max_amount_decimal = FLAG_21[invoice["flag_21"]]["max_amount_decimal"]
        max_payment_amount_int = FLAG_21[invoice["flag_21"]]["max_payment_amount_int"]
        max_payment_amount_decimal = FLAG_21[invoice["flag_21"]]["max_payment_amount_decimal"]
        max_qty_int = FLAG_21[invoice["flag_21"]]["max_qty_int"]
        max_qty_decimal = FLAG_21[invoice["flag_21"]]["max_qty_decimal"]
        disc_int = FLAG_21[invoice["flag_21"]]["disc_int"]
        disc_decimal = FLAG_21[invoice["flag_21"]]["disc_decimal"]

        try:
            last_trama = self._States("S1")
            last_res = S1PrinterData(last_trama)
            last_number = last_res.__dict__["_lastNCNumber"]
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            cmd.append(str("iR*" + invoice["partner_id"]["vat"]))
            cmd.append(str("iS*" + invoice["partner_id"]["name"]))
            cmd.append(str("iF*" + invoice["invoice_affected"]["number"]))
            cmd.append(str("iI*" + invoice["invoice_affected"]["serial_machine"]))
            cmd.append(str("iD*" + invoice["invoice_affected"]["date"]))
            if invoice["partner_id"]["address"]:
                cmd.append(str("i00Direccion:" + invoice["partner_id"]["address"]))
            if invoice["partner_id"]["phone"]:
                cmd.append(str("i01Telefono:" + invoice["partner_id"]["phone"]))

            if len(invoice.get("info", [])) > 0:
                for index, info in enumerate(invoice.get("info")):
                    cmd.append(f"i{str(index+2).zfill(2)}{info}")

            discount_amount = 0

            for item in invoice["invoice_lines"]:
                if item.get("price_unit", 0) < 0:
                    discount_amount += abs(item.get("price_unit", 0))
                    continue

                code = ""
                if item.get("code", False):
                    code = "|" + item.get("code", "") + "|"

                amount_i, amount_d = self.split_amount(
                    abs(round(item["price_unit"], max_amount_decimal)),
                    dec=max_amount_decimal,
                )
                qty_i, qty_d = self.split_amount(item["quantity"], dec=max_qty_decimal)

                if invoice.get("traditional_line", True):
                    cmd.append(
                        str(
                            "d"
                            + str(item.get("tax", "0"))
                            + amount_i.zfill(max_amount_int)
                            + amount_d.zfill(max_amount_decimal)
                            + qty_i.zfill(max_qty_int)
                            + qty_d.zfill(max_qty_decimal)
                            + f"{code}"
                            + item["name"][0:127].strip().replace("Ñ", "N").replace("ñ", "n")
                        )
                    )
                else:
                    cmd.append(
                        str(
                            "GC+"
                            + str(item["tax"])
                            + amount_i.zfill(max_amount_int)
                            + ","
                            + amount_d.zfill(max_amount_decimal)
                            + "||"
                            + qty_i.zfill(max_qty_int)
                            + ","
                            + qty_d.zfill(max_qty_decimal)
                            + "||"
                            + code
                            + item["name"][0:127].replace("Ñ", "N").replace("ñ", "n")
                        )
                    )

                if item.get("discount", 0) > 0:
                    amount_i, amount_d = self.split_amount(
                        round(item.get("discount"), disc_decimal), dec=disc_decimal
                    )
                    cmd.append(f"p-{amount_i.zfill(2)}{amount_d.zfill(2)}")
                if len(invoice.get("barcode", [])) > 0:
                 number = invoice.get("barcode")
                 numberint = number[0]
                 cmd.append(str("y" + str(numberint)))
            cmd.append(str("3"))  # sub total en factura

            if discount_amount > 0:
                amount_i, amount_d = self.split_amount(
                    round(discount_amount, disc_decimal), dec=disc_decimal
                )
                cmd.append("q-" + amount_i.zfill(disc_int) + amount_d.zfill(disc_decimal))

            def filter_unique_type_method(payment):
                return payment["payment_method"] == "20"

            new_payment_lines = []
            for item in invoice["payment_lines"]:
                if item["payment_method"] not in [
                    payment["payment_method"] for payment in new_payment_lines
                ]:
                    new_payment_lines.append(item)
                    continue

                for value in new_payment_lines:
                    if item["payment_method"] == value["payment_method"]:
                        value["amount"] += item["amount"]

            if invoice.get("has_cashbox", False):
                cmd.append("w")

            for item in new_payment_lines:
                item["amount"] = abs(item["amount"])

            if len(invoice["payment_lines"]) == 1 or invoice["payment_lines"][0]["amount"] == 0:
                cmd.append("1" + str(invoice["payment_lines"][0]["payment_method"]))
            elif len(invoice["payment_lines"]) > 1 and len(
                list(filter(filter_unique_type_method, invoice["payment_lines"]))
            ) == len(invoice["payment_lines"]):
                cmd.append("1" + str(invoice["payment_lines"][0]["payment_method"]))
            else:
                for item in new_payment_lines:
                    amount_i, amount_d = self.split_amount(
                        item["amount"],
                        dec=max_payment_amount_decimal,
                    )
                    cmd.append(
                        "2"
                        + str(
                            (item["payment_method"] or "01")
                            + amount_i.zfill(max_payment_amount_int)
                            + amount_d
                        )
                    )

            cmd.append(str("101"))
            if len(invoice.get("aditional_lines", [])) > 0:
                for index, aditional_lines in enumerate(invoice.get("aditional_lines")):
                    cmd.append(f"i{str(index).zfill(2)}{aditional_lines}")
            cmd.append(str("199"))

            for command in cmd:
                self.SendCmd(command)

            msg = "Nota de credito impresa correctamente"
            trama = self._States("S1")
            res = S1PrinterData(trama)
            number = res.__dict__.get("_lastNCNumber", "")
            number_z = res.__dict__.get("_dailyClosureCounter", "")
            machine_number = res.__dict__.get("_registeredMachineNumber", "")

            if number == last_number:
                return {"valid": False, "message": "No se imprimio el documento"}

            machine = {
                "valid": True,
                "data": {
                    "sequence": number,
                    "serial_machine": machine_number,
                    "mf_reportz": number_z + 1,
                },
            }

        except Exception as _e:
            _logger.warning(cmd)
            valid = False
            machine = False
            msg = str(_e)

        response = {"valid": valid, "message": msg}
        if machine:
            response.update(machine["data"])
            _logger.warning(response)

        return response

    def print_debit_note(self, invoice):
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

        self.data["value"] = self._print_debit_note(invoice)
        event_manager.device_changed(self)
        return self.data["value"]
                
    def _print_debit_note(self, invoice):
        valid = True
        cmd = []

        max_amount_int = FLAG_21[invoice["flag_21"]]["max_amount_int"]
        max_amount_decimal = FLAG_21[invoice["flag_21"]]["max_amount_decimal"]
        max_payment_amount_int = FLAG_21[invoice["flag_21"]]["max_payment_amount_int"]
        max_payment_amount_decimal = FLAG_21[invoice["flag_21"]]["max_payment_amount_decimal"]
        max_qty_int = FLAG_21[invoice["flag_21"]]["max_qty_int"]
        max_qty_decimal = FLAG_21[invoice["flag_21"]]["max_qty_decimal"]
        disc_int = FLAG_21[invoice["flag_21"]]["disc_int"]
        disc_decimal = FLAG_21[invoice["flag_21"]]["disc_decimal"]

        try:
            last_trama = self._States("S1")
            last_res = S1PrinterData(last_trama)
            last_number = last_res.__dict__["_lastNCNumber"]
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            cmd.append(str("iR*" + invoice["partner_id"]["vat"]))
            cmd.append(str("iS*" + invoice["partner_id"]["name"]))
            cmd.append(str("iF*" + invoice["invoice_affected"]["number"]))
            cmd.append(str("iI*" + invoice["invoice_affected"]["serial_machine"]))
            cmd.append(str("iD*" + invoice["invoice_affected"]["date"]))
            if invoice["partner_id"]["address"]:
                cmd.append(str("i00Direccion:" + invoice["partner_id"]["address"]))
            if invoice["partner_id"]["phone"]:
                cmd.append(str("i01Telefono:" + invoice["partner_id"]["phone"]))

            if len(invoice.get("info", [])) > 0:
                for index, info in enumerate(invoice.get("info")):
                    cmd.append(f"i{str(index+2).zfill(2)}{info}")

            discount_amount = 0

            for item in invoice["invoice_lines"]:
                if item.get("price_unit", 0) < 0:
                    discount_amount += abs(item.get("price_unit", 0))
                    continue

                code = ""
                if item.get("code", False):
                    code = "|" + item.get("code", "") + "|"

                amount_i, amount_d = self.split_amount(
                    abs(round(item["price_unit"], max_amount_decimal)),
                    dec=max_amount_decimal,
                )
                qty_i, qty_d = self.split_amount(item["quantity"], dec=max_qty_decimal)

                if invoice.get("traditional_line", True):
                    cmd.append(
                        str(
                            "`"
                            + str(item.get("tax", "0"))
                            + amount_i.zfill(max_amount_int)
                            + amount_d.zfill(max_amount_decimal)
                            + qty_i.zfill(max_qty_int)
                            + qty_d.zfill(max_qty_decimal)
                            + f"{code}"
                            + item["name"][0:127].strip().replace("Ñ", "N").replace("ñ", "n")
                        )
                    )
                # else:
                #     cmd.append(
                #         str(
                #             "GC+"
                #             + str(item["tax"])
                #             + amount_i.zfill(max_amount_int)
                #             + ","
                #             + amount_d.zfill(max_amount_decimal)
                #             + "||"
                #             + qty_i.zfill(max_qty_int)
                #             + ","
                #             + qty_d.zfill(max_qty_decimal)
                #             + "||"
                #             + code
                #             + item["name"][0:127].replace("Ñ", "N").replace("ñ", "n")
                #         )
                #     )

                if item.get("discount", 0) > 0:
                    amount_i, amount_d = self.split_amount(
                        round(item.get("discount"), disc_decimal), dec=disc_decimal
                    )
                    cmd.append(f"p-{amount_i.zfill(2)}{amount_d.zfill(2)}")
                if len(invoice.get("barcode", [])) > 0:
                 number = invoice.get("barcode")
                 numberint = number[0]
                 cmd.append(str("y" + str(numberint)))
            cmd.append(str("3"))  # sub total en factura

            if discount_amount > 0:
                amount_i, amount_d = self.split_amount(
                    round(discount_amount, disc_decimal), dec=disc_decimal
                )
                cmd.append("q-" + amount_i.zfill(disc_int) + amount_d.zfill(disc_decimal))

            def filter_unique_type_method(payment):
                return payment["payment_method"] == "20"

            new_payment_lines = []
            for item in invoice["payment_lines"]:
                if item["payment_method"] not in [
                    payment["payment_method"] for payment in new_payment_lines
                ]:
                    new_payment_lines.append(item)
                    continue

                for value in new_payment_lines:
                    if item["payment_method"] == value["payment_method"]:
                        value["amount"] += item["amount"]

            if invoice.get("has_cashbox", False):
                cmd.append("w")

            for item in new_payment_lines:
                item["amount"] = abs(item["amount"])

            if len(invoice["payment_lines"]) == 1 or invoice["payment_lines"][0]["amount"] == 0:
                cmd.append("1" + str(invoice["payment_lines"][0]["payment_method"]))
            elif len(invoice["payment_lines"]) > 1 and len(
                list(filter(filter_unique_type_method, invoice["payment_lines"]))
            ) == len(invoice["payment_lines"]):
                cmd.append("1" + str(invoice["payment_lines"][0]["payment_method"]))
            else:
                for item in new_payment_lines:
                    amount_i, amount_d = self.split_amount(
                        item["amount"],
                        dec=max_payment_amount_decimal,
                    )
                    cmd.append(
                        "2"
                        + str(
                            (item["payment_method"] or "01")
                            + amount_i.zfill(max_payment_amount_int)
                            + amount_d
                        )
                    )

            cmd.append(str("101"))
            if len(invoice.get("aditional_lines", [])) > 0:
                for index, aditional_lines in enumerate(invoice.get("aditional_lines")):
                    cmd.append(f"i{str(index).zfill(2)}{aditional_lines}")
            cmd.append(str("199"))

            for command in cmd:
                self.SendCmd(command)

            msg = "Nota de debito impresa correctamente"
            trama = self._States("S1")
            res = S1PrinterData(trama)
            number = res.__dict__.get("_lastDebtNoteNumber", "")
            number_z = res.__dict__.get("_dailyClosureCounter", "")
            machine_number = res.__dict__.get("_registeredMachineNumber", "")
            
            
            if number == last_number:
                return {"valid": False, "message": "No se imprimio el documento"}

            machine = {
                "valid": True,
                "data": {
                    "sequence": number,
                    "serial_machine": machine_number,
                    "mf_reportz": number_z + 1,
                },
            }

        except Exception as _e:
            _logger.warning(cmd)
            valid = False
            machine = False
            msg = str(_e)

        response = {"valid": valid, "message": msg}
        if machine:
            response.update(machine["data"])
            _logger.warning(response)

        return response
    
    def _print_out_invoice(self, invoice):
        valid = True
        cmd = []

        max_amount_int = FLAG_21[invoice["flag_21"]]["max_amount_int"]
        max_amount_decimal = FLAG_21[invoice["flag_21"]]["max_amount_decimal"]
        max_payment_amount_int = FLAG_21[invoice["flag_21"]]["max_payment_amount_int"]
        max_payment_amount_decimal = FLAG_21[invoice["flag_21"]]["max_payment_amount_decimal"]
        max_qty_int = FLAG_21[invoice["flag_21"]]["max_qty_int"]
        max_qty_decimal = FLAG_21[invoice["flag_21"]]["max_qty_decimal"]
        disc_int = FLAG_21[invoice["flag_21"]]["disc_int"]
        disc_decimal = FLAG_21[invoice["flag_21"]]["disc_decimal"]

        try:
            last_trama = self._States("S1")
            last_res = S1PrinterData(last_trama)
            last_number = last_res.__dict__["_lastInvoiceNumber"]
            _logger.info("last_number %s", last_number)
            _logger.info(type(last_number))

            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            cmd.append(str("iR*" + invoice["partner_id"]["vat"]))
            cmd.append(str("iS*" + invoice["partner_id"]["name"]))
            if invoice["partner_id"]["address"]:
                cmd.append(str("i00Direccion:" + invoice["partner_id"]["address"]))
            if invoice["partner_id"]["phone"]:
                cmd.append(str("i01Telefono:" + invoice["partner_id"]["phone"]))

            if len(invoice.get("info", [])) > 0:
                for index, info in enumerate(invoice.get("info")):
                    cmd.append(f"i{str(index+2).zfill(2)}{info}")

            discount_amount = 0

            for item in invoice["invoice_lines"]:
                if item.get("price_unit", 0) < 0:
                    discount_amount += abs(item.get("price_unit", 0))
                    continue

                code = ""
                if item.get("code", False):
                    code = "|" + item.get("code", "") + "|"

                amount_i, amount_d = self.split_amount(
                    abs(round(item["price_unit"], max_amount_decimal)),
                    dec=max_amount_decimal,
                )
                qty_i, qty_d = self.split_amount(item["quantity"], dec=max_qty_decimal)

                if invoice.get("traditional_line", True):
                    cmd.append(
                        str(
                            TAX.get(str(item.get("tax", " ")), " ")
                            + amount_i.zfill(max_amount_int)
                            + amount_d.zfill(max_amount_decimal)
                            + qty_i.zfill(max_qty_int)
                            + qty_d.zfill(max_qty_decimal)
                            + f"{code}"
                            + item["name"][0:127].strip().replace("Ñ", "N").replace("ñ", "n")
                        )
                    )
                else:
                    cmd.append(
                        str(
                            "GF+"
                            + str(item["tax"])
                            + amount_i.zfill(14)
                            + ","
                            + amount_d.zfill(2)
                            + "||"
                            + qty_i.zfill(14)
                            + ","
                            + qty_d.zfill(3)
                            + "||"
                            + code
                            + item["name"][0:127]
                        )
                    )
                if item.get("discount", 0) > 0:
                    amount_i, amount_d = self.split_amount(
                        round(item.get("discount"), disc_decimal), dec=disc_decimal
                    )
                    cmd.append(f"p-{amount_i.zfill(2)}{amount_d.zfill(2)}")
            if len(invoice.get("barcode", [])) > 0:
                number = invoice.get("barcode")
                numberint = number[0]
                cmd.append(str("y" + str(numberint))) 
            cmd.append(str("3"))  # sub total en factura 
            if discount_amount > 0:
                amount_i, amount_d = self.split_amount(
                    round(discount_amount, disc_decimal), dec=disc_decimal
                )
                cmd.append("q-" + amount_i.zfill(disc_int) + amount_d.zfill(disc_decimal))

            def filter_unique_type_method(payment):
                return payment["payment_method"] == "20"

            new_payment_lines = []
            for item in invoice["payment_lines"]:
                if item["payment_method"] not in [
                    payment["payment_method"] for payment in new_payment_lines
                ]:
                    new_payment_lines.append(item)
                    continue

                for value in new_payment_lines:
                    if item["payment_method"] == value["payment_method"]:
                        value["amount"] += item["amount"]

            if invoice.get("has_cashbox", False):
                cmd.append("w")

            for item in new_payment_lines:
                item["amount"] = abs(item["amount"])

            if len(invoice["payment_lines"]) == 1 or invoice["payment_lines"][0]["amount"] == 0:
                cmd.append("1" + str(invoice["payment_lines"][0]["payment_method"]))
            elif len(invoice["payment_lines"]) > 1 and len(
                list(filter(filter_unique_type_method, invoice["payment_lines"]))
            ) == len(invoice["payment_lines"]):
                cmd.append("1" + str(invoice["payment_lines"][0]["payment_method"]))
            else:
                for item in new_payment_lines:
                    amount_i, amount_d = self.split_amount(
                        item["amount"],
                        dec=max_payment_amount_decimal,
                    )
                    cmd.append(
                        "2"
                        + str(
                            (item["payment_method"] or "01")
                            + amount_i.zfill(max_payment_amount_int)
                            + amount_d
                        )
                    )

            cmd.append(str("101"))

            if len(invoice.get("aditional_lines", [])) > 0:
                for index, aditional_lines in enumerate(invoice.get("aditional_lines")):
                    cmd.append(f"i{str(index).zfill(2)}{aditional_lines}")

            cmd.append(str("199"))

            for command in cmd:
                self.SendCmd(command)

            msg = "Factura impresa correctamente"
            trama = self._States("S1")
            res = S1PrinterData(trama)
            number = res.__dict__.get("_lastInvoiceNumber", "")
            number_z = res.__dict__.get("_dailyClosureCounter", "")
            machine_number = res.__dict__.get("_registeredMachineNumber", "")

            if number == last_number:
                return {"valid": False, "message": "No se imprimio el documento"}

            machine = {
                "valid": True,
                "data": {
                    "sequence": number,
                    "serial_machine": machine_number,
                    "mf_reportz": number_z + 1,
                },
            }

        except Exception as _e:
            _logger.warning(cmd)
            valid = False
            machine = False
            msg = str(_e)

        response = {"valid": valid, "message": msg}
        if machine:
            response.update(machine["data"])

        return response

    def split_amount(self, amount, dec=2):
        txt = "{price:.2f}"
        if dec == 3:
            txt = "{price:.3f}"
        if dec == 4:
            txt = "{price:.4f}"
        amount_str = txt.format(price=amount)
        amounts = str(amount_str).split(".")
        return amounts[0], amounts[1]

    def get_last_out_refund_number(self, data):
        try:
            estado_s1 = self.GetS1PrinterData(True)
            number = estado_s1["data"]["_lastNCNumber"]
            machine_number = estado_s1["data"]["_registeredMachineNumber"]
            response = {
                "valid": True,
                "data": {"sequence": number, "serial_machine": machine_number},
            }

            self.data["value"] = response
            event_manager.device_changed(self)
            return response
        except Exception as _e:
            _logger.warning("Exception %s", str(_e))
            return str(_e)

    def get_last_invoice_number(self, data):
        try:
            estado_s1 = self.GetS1PrinterData(True)
            number = estado_s1["data"]["_lastInvoiceNumber"]
            machine_number = estado_s1["data"]["_registeredMachineNumber"]
            response = {
                "valid": True,
                "data": {"sequence": number, "serial_machine": machine_number},
            }

            self.data["value"] = response
            event_manager.device_changed(self)
            return response
        except Exception as _e:
            _logger.warning("exepcion %s", str(_e))
            return str(_e)

    def pre_invoice(self, invoice):
        valid, _msg = self._validate_invoice_parameter(invoice)
        msg = "Factura validada."
        if len(_msg) > 0:
            msg = ", ".join(_msg)
        self.data["value"] = {"valid": valid, "message": msg}
        event_manager.device_changed(self)

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
            msg.append("No se recibio informacion de la factura afecatada")
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
            msg.append("No se recibio la fecha de la factura afecada")
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

    def programacion(self, data):
        self.SendCmd("D")
        self.data["value"] = {"valid": True, "message": "Programacion Impresa"}
        event_manager.device_changed(self)
        return self.data["value"]

    def _HandleCTSRTS(self):
        return True  # CTS está activado, éxito

    def SendCmd(self, cmd):
        connection = self._connection
        if cmd == "I0X" or cmd == "I1X" or cmd == "I1Z":
            self.trama = self._States_Report(cmd, 4)
            return self.trama
        if cmd == "I0Z":
            self.trama = self._States_Report(cmd, 9)
            return self.trama
        else:
            try:
                connection.reset_output_buffer()
                connection.reset_input_buffer()
                if self._HandleCTSRTS():
                    msj = self._AssembleQueryToSend(cmd)
                    self._write(msj)
                    time.sleep(0.5)
                    tries = 0
                    rt = ""
                    while rt == "" and tries < 60:
                        rt = self._read(1)
                        if tries > 0:
                            _logger.info("RETRY: %s", tries)
                        tries += 1
                    if rt == chr(0x06):
                        self.envio = "Status: 00  Error: 00"
                        rt = True
                    else:
                        self.envio = "Status: 00  Error: 89"
                        rt = False
                else:
                    self._GetStatusError(0, 128)
                    self.envio = "Error... CTS in False"
                    rt = False
            except serial.SerialException:
                rt = False
            return rt

    def SendCmdFile(self, f):
        for linea in f:
            if linea != "":
                self.SendCmd(linea)

    def _QueryCmd(self, cmd):
        connection = self._connection
        try:
            connection.reset_input_buffer()
            connection.reset_output_buffer()
            msj = self._AssembleQueryToSend(cmd)
            self._write(msj)
            rt = True
        except serial.SerialException:
            rt = False
        return rt

    def _FetchRow(self):
        connection = self._connection
        _logger.info("FetchRow")
        while True:
            time.sleep(1)
            int_bytes = connection.in_waiting
            tries = 1
            while int_bytes == 0 and tries < 10:
                _logger.info("retry: %s", tries)
                time.sleep(1)
                tries += 1
                int_bytes = connection.in_waiting

            _logger.info("Bytes: %s", int_bytes)
            if int_bytes > 1:
                msj = self._read(int_bytes)
                linea = msj[1:-1]
                lrc = chr(self._Lrc(linea))
                if lrc == msj[-1]:
                    connection.reset_input_buffer()
                    connection.reset_output_buffer()
                    return msj
                else:
                    _logger.info("BREAk1")
                    break
            else:
                _logger.info("break2")
                break
        return None

    def _FetchRow_Report(self, r):
        connection = self._connection
        while True:
            time.sleep(r)
            bytes = connection.in_waiting
            if bytes > 0:
                msj = self._read(bytes)
                linea = msj
                lrc = chr(self._Lrc(linea))
                if lrc == msj:
                    connection.reset_input_buffer()
                    connection.reset_output_buffer()
                    return msj
                else:
                    return msj
                    break
            else:
                break
        return None

    def get_status_machine(self, data):
        response = self.ReadFpStatus(True)
        self.data["value"] = response
        event_manager.device_changed(self)
        return response

    def ReadFpStatus(self, data):
        msj = chr(0x05)
        self._write(msj)
        time.sleep(0.05)
        r = self._read(5)
        if len(r) == 5:
            if ord(r[1]) ^ ord(r[2]) ^ 0x03 == ord(r[4]):
                status = self._GetStatusError(ord(r[1]), ord(r[2]))
                return {
                    "valid": True,
                    "message": f"""
                {status['status']['code']}: {status['status']['msg']}
                {status['error']['code']}: {status['error']['msg']}
                """,
                    "data": status,
                }
            status = self._GetStatusError(0, 144)
            return {
                "valid": True,
                "message": f"""
            {status['status']['code']}: {status['status']['msg']}
            {status['error']['code']}: {status['error']['msg']}
            """,
                "data": status,
            }
        _logger.info("3")
        status = self._GetStatusError(0, 114)
        return {
            "valid": True,
            "message": f"""
        {status['status']['code']}: {status['status']['msg']}
        {status['error']['code']}: {status['error']['msg']}
        """,
            "data": status,
        }

    def _write(self, msj):
        connection = self._connection
        _logger.info("WRITE: %s", msj.encode("latin-1"))
        connection.write(msj.encode("latin-1"))

    def _read(self, bytes):
        connection = self._connection
        msj = connection.read(bytes)
        _logger.info("READ: %s", msj)
        return msj.decode()

    def _AssembleQueryToSend(self, linea):
        lrc = self._Lrc(linea + chr(0x03))
        previo = chr(0x02) + linea + chr(0x03) + chr(lrc)
        return previo

    def _Lrc(self, linea):
        if isinstance(linea, str):
            variable = reduce(operator.xor, list(map(ord, str(linea))))
        else:
            variable = reduce(operator.xor, map(ord, list(linea.decode("latin-1"))))
        if self.mdepura:
            self._Debug(linea)
        # print('map reduce: ' + str(variable))
        return variable

    def _Debug(self, linea):
        if linea != None:
            if len(linea) == 0:
                return "null"
            if len(linea) > 3:
                lrc = linea[-1]
                linea = linea[0:-1]
                adic = " LRC(" + str(ord(str(lrc))) + ")"
                # adic = ' LRC('+str(lrc)+')'
            else:
                adic = ""
            linea = linea.replace("STX", chr(0x02), 1)
            linea = linea.replace("ENQ", chr(0x05), 1)
            linea = linea.replace("ETX", chr(0x03), 1)
            linea = linea.replace("EOT", chr(0x04), 1)
            linea = linea.replace("ACK", chr(0x06), 1)
            linea = linea.replace("NAK", chr(0x15), 1)
            linea = linea.replace("ETB", chr(0x17), 1)

        return linea + adic

    def _States(self, cmd):
        # print cmd
        self._QueryCmd(cmd)
        while True:
            trama = self._FetchRow()
            # print("La trama es" + trama + "hasta aca")
            if trama == None:
                break
            return trama

    def _States_Report(self, cmd, r):
        # print cmd
        ret = r
        self._QueryCmd(cmd)
        while True:
            trama = self._FetchRow_Report(ret)
            # print "La trama es", trama, "hasta aca"
            if trama == None:
                break
            return trama

    def _UploadDataReport(self, cmd):
        connection = self._connection
        try:
            connection.reset_input_buffer()
            connection.reset_output_buffer()
            if self._HandleCTSRTS():
                msj = 1
                msj = self._AssembleQueryToSend(cmd)
                self._write(msj)
                retries = 0
                while True and retries < 3:
                    rt = self._read(1)
                    if rt != None:
                        time.sleep(0.05)
                        msj = self._Debug("ACK")
                        self._write(msj)
                        time.sleep(0.05)
                        msj = self._FetchRow()
                        return msj
                    else:
                        self._GetStatusError(0, 128)
                        self.envio = "Error... CTS in False"
                        rt = None
                        connection.setRTS(False)
                    retries += 1
        except serial.SerialException:
            rt = None
            return rt

    def _ReadFiscalMemoryByNumber(self, cmd):
        msj = ""
        arreglodemsj = []
        counter = 0
        connection = self._connection
        try:
            connection.reset_input_buffer()
            connection.reset_output_buffer()
            if self._HandleCTSRTS():
                m = ""
                msj = self._AssembleQueryToSend(cmd)
                self._write(msj)
                rt = self._read(1)
                while True:
                    while msj != chr(0x04):
                        time.sleep(0.5)
                        msj = self._Debug("ACK")
                        self._write(msj)
                        time.sleep(0.5)
                        msj = self._FetchRow_Report(1.3)
                        if msj == None:
                            counter += 1
                        else:
                            arreglodemsj.append(msj)
                    return arreglodemsj
            else:
                self._GetStatusError(0, 128)
                self.envio = "Error... CTS in False"
                m = None
                connection.setRTS(False)
        except serial.SerialException:
            m = None
        return m

    def _ReadFiscalMemoryByDate(self, cmd):
        connection = self._connection
        msj = ""
        arreglodemsj = []
        counter = 0
        try:
            connection.reset_input_buffer()
            connection.reset_output_buffer()
            if self._HandleCTSRTS():
                m = ""
                msj = self._AssembleQueryToSend(cmd)
                self._write(msj)
                rt = self._read(1)
                while True:
                    while msj != chr(0x04):
                        time.sleep(0.5)
                        msj = self._Debug("ACK")
                        self._write(msj)
                        time.sleep(0.5)
                        msj = self._FetchRow_Report(1.5)
                        if msj == None:
                            counter += 1
                        else:
                            arreglodemsj.append(msj)
                    return arreglodemsj
            else:
                self._GetStatusError(0, 128)
                self.envio = "Error... CTS in False"
                m = None
                connection.setRTS(False)
        except serial.SerialException:
            m = None
        return m

    def GetS1PrinterData(self, data):
        self.trama = self._States("S1")
        res = S1PrinterData(self.trama)
        self.data["value"] = {
            "valid": True,
            "data": res.__dict__,
            "message": "S1 Consultado con exito",
        }
        event_manager.device_changed(self)
        return self.data["value"]

    def GetS2PrinterData(self):
        return S2PrinterData(self._States("S2"))

    def GetS25PrinterData(self):
        self.trama = self._States("S25")
        # print self.trama
        self.S25PrinterData = S25PrinterData(self.trama)
        return self.S25PrinterData

    def GetS3PrinterData(self):
        self.trama = self._States("S3")
        # print self.trama
        self.S3PrinterData = S3PrinterData(self.trama)
        return self.S3PrinterData

    def GetS4PrinterData(self):
        self.trama = self._States("S4")
        # print self.trama
        self.S4PrinterData = S4PrinterData(self.trama)
        return self.S4PrinterData

    def GetS5PrinterData(self):
        self.trama = self._States("S5")
        # print self.trama
        self.S5PrinterData = S5PrinterData(self.trama)
        return self.S5PrinterData

    def GetS6PrinterData(self):
        self.trama = self._States("S6")
        # print self.trama
        self.S6PrinterData = S6PrinterData(self.trama)
        return self.S6PrinterData

    def GetS7PrinterData(self):
        self.trama = self._States("S7")
        # print self.trama
        self.S7PrinterData = S7PrinterData(self.trama)
        return self.S7PrinterData

    def GetS8EPrinterData(self):
        self.trama = self._States("S8E")
        # print self.trama
        self.S8EPrinterData = S8EPrinterData(self.trama)
        return self.S8EPrinterData

    def GetS8PPrinterData(self):
        self.trama = self._States("S8P")
        # print self.trama
        self.S8PPrinterData = S8PPrinterData(self.trama)
        return self.S8PPrinterData

    def GetXReport(self):
        self.trama = self._UploadDataReport("U0X")
        # print self.trama
        self.XReport = ReportData(self.trama)
        return self.XReport

    def GetX2Report(self):
        self.trama = self._UploadDataReport("U1X")
        # print self.trama
        self.XReport = ReportData(self.trama)
        return self.XReport

    def GetX4Report(self):
        self.trama = self._UploadDataReport("U0X4")
        # print self.trama
        self.XReport = AcumuladosX(self.trama)
        return self.XReport

    def GetX5Report(self):
        self.trama = self._UploadDataReport("U0X5")
        # print self.trama
        self.XReport = AcumuladosX(self.trama)
        return self.XReport

    def GetX7Report(self):
        self.trama = self._UploadDataReport("U0X7")
        # print self.trama
        self.XReport = AcumuladosX(self.trama)
        return self.XReport

    def GetZReport(self, *items):
        if len(items) > 0:
            mode = items[0]
            startParam = items[1]
            endParam = items[2]
            if type(startParam) == datetime.date and type(endParam) == datetime.date:
                starString = startParam.strftime("%d%m%y")
                endString = endParam.strftime("%d%m%y")
                cmd = "U2" + mode + starString + endString
                self.trama = self._ReadFiscalMemoryByDate(cmd)
            else:
                starString = str(startParam)
                while len(starString) < 6:
                    starString = "0" + starString
                endString = str(endParam)
                while len(endString) < 6:
                    endString = "0" + endString
                cmd = "U3" + mode + starString + endString
                self.trama = self._ReadFiscalMemoryByNumber(cmd)
            self.ReportData = []
            i = 0
            for report in self.trama[0:-1]:
                self.Z = ReportData(report)
                self.ReportData.append(self.Z)
                i += 1
        else:
            self.trama = self._UploadDataReport("U0Z")
            self.ReportData = ReportData(self.trama)
        return self.ReportData

    def PrintXReport(self, action):
        self.trama = self._States_Report("I0X", 4)
        response = {"valid": True, "message": "Impreso con exito"}
        self.data["value"] = response
        event_manager.device_changed(self)
        return response

    def PrintZReport(self, data, *items):# (self, mode, startParam, endParam):
        status = self.ReadFpStatus(True)
        if status["data"]["error"]["code"] != "0":
            raise Exception(status["data"]["error"]["msg"])
        if status["data"]["status"]["code"] not in ["1", "4"]:
            raise Exception(status["data"]["status"]["msg"])
        if len(items) > 0:
            mode = items[0]
            startParam = items[1]
            endParam = items[2]

            rep = False

            # if(type(startParam)==int and (type(endParam)==int)):
            if type(startParam) == datetime.date and type(endParam) == datetime.date:
                starString = startParam.strftime("%d%m%y")
                endString = endParam.strftime("%d%m%y")
                cmd = "I2" + mode + starString + endString
                rep = self.SendCmd("I2" + mode + starString + endString)
            else:
                starString = str(startParam)
                while len(starString) < 6:
                    starString = "0" + starString
                endString = str(endParam)
                while len(endString) < 6:
                    endString = "0" + endString
                rep = self.SendCmd("I3" + mode + starString + endString)
                if rep == False:
                    if starString > endString:
                        # raise(Estado)
                        estado = "The original number can not be greater than the final number"
        else:
            self.data["value"] = {
                "valid": False,
                "message": "No se completo el reporte Z",
            }
            data_s1 = self.GetS1PrinterData(True).get("data", {})
            self.trama = self._States_Report("I0Z", 9)
            self.data["value"] = {
                "valid": True,
                "message": "Reporte Z Impreso correctamente",
                "data": data_s1,
            }
            event_manager.device_changed(self)
            return self.data["value"]

    def _GetStatusError(self, st, er):
        st_aux = st
        st = st & ~0x04

        status = {
            "msg": "Status Desconocido",
            "code": "#",
        }
        error = {"msg": "Error Desconocido", "code": "#"}

        status_codes = {
            "0x6A": {
                "msg": "En modo fiscal, carga completa de la memoria fiscal "
                + "y emisi�n de documentos no fiscales",
                "code": "12",
            },
            "0x69": {
                "msg": "En modo fiscal, carga completa de la memoria fiscal "
                + "y emisi�n de documentos  fiscales",
                "code": "11",
            },
            "0x68": {
                "msg": "En modo fiscal, carga completa de la memoria fiscal y en espera",
                "code": "10",
            },
            "0x72": {
                "msg": "En modo fiscal, cercana carga completa de la memoria fiscal "
                + "y en emision de documentos no fiscales",
                "code": "9",
            },
            "0x71": {
                "msg": "En modo fiscal, cercana carga completa de la memoria fiscal "
                + "y en emisi�n de documentos no fiscales",
                "code": "8",
            },
            "0x70": {
                "msg": "En modo fiscal, cercana carga completa de la memoria fiscal y en espera",
                "code": "7",
            },
            "0x62": {"msg": "En modo fiscal y en emision de documentos no fiscales", "code": "6"},
            "0x61": {"msg": "En modo fiscal y en emision de documentos fiscales", "code": "5"},
            "0x60": {"msg": "En modo fiscal y en espera", "code": "4"},
            "0x42": {"msg": "En modo prueba y en emision de documentos no fiscales", "code": "3"},
            "0x41": {"msg": "En modo prueba y en emision de documentos fiscales", "code": "2"},
            "0x40": {"msg": "En modo prueba y en espera", "code": "1"},
            "0x00": {"msg": "Status Desconocido", "code": "0"},
            "0x0": {"msg": "Status Desconocido", "code": "0"},
        }

        error_codes = {
            "0x80": {"msg": "CTS en falso", "code": "128"},
            "0x89": {"msg": "No hay respuesta", "code": "137"},
            "0x90": {"msg": "Error LRC", "code": "144"},
            "0x72": {"msg": "Impresora no responde u ocupada", "code": "114"},
            "0x6C": {"msg": "Memoria Fiscal llena", "code": "108"},
            "0x64": {"msg": "Error en memoria fiscal", "code": "100"},
            "0x60": {"msg": "Error Fiscal", "code": "96"},
            "0x5C": {"msg": "Comando Invalido", "code": "92"},
            "0x58": {"msg": "No hay asignadas  directivas", "code": "88"},
            "0x54": {"msg": "Tasa Invalida", "code": "84"},
            "0x50": {"msg": "Comando Invalido/Valor Invalido", "code": "80"},
            "0x48": {"msg": "Error Gaveta", "code": "0"},
            "0x43": {"msg": "Fin en la entrega de papel y error mecanico", "code": "3"},
            "0x42": {"msg": "Error de indole mecanico en la entrega de papel", "code": "2"},
            "0x41": {"msg": "Fin en la entrega de papel", "code": "1"},
            "0x40": {"msg": "Sin error", "code": "0"},
        }

        if hex(st) in status_codes:
            status = status_codes[hex(st)]
        if hex(er) in error_codes:
            error = error_codes[hex(er)]
        if hex(st_aux) == "0x04":
            error = {"msg": "Buffer Completo", "code": "112"}

        return {"status": status, "error": error}
