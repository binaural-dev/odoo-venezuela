import logging
import serial
import serial.tools.list_ports
import requests

from odoo import _
from odoo.addons.hw_drivers.event_manager import event_manager
from .FiscalDriver import SerialProtocol, SerialBaseFiscalDriver
from odoo.addons.hw_drivers.iot_handlers.drivers.SerialBaseDriver import (
    serial_connection,
)

_logger = logging.getLogger(__name__)


FiscalProtocol = SerialProtocol(
    name="PnP FiscalMachine",
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    stopbits=serial.STOPBITS_ONE,
    parity=serial.PARITY_EVEN,
    timeout=2,
    writeTimeout=5,
    commandDelay=0.2,
    measureDelay=0.2,
)

TAX = {
    "0": "0000",
    "1": "1600",
    "2": "0800",
    "3": "3100",
}


class SerialPnPFiscalDriver(SerialBaseFiscalDriver):
    connection_type = "serial"
    _protocol = FiscalProtocol

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self.identifier = identifier
        self._set_actions()

    @classmethod
    def supported(cls, device):
        protocol = cls._protocol
        try:
            with serial_connection(device["identifier"], protocol) as connection:
                connection.reset_output_buffer()
                connection.reset_input_buffer()

                msj = _wrap_low_level_message_around("8|N")
                write_message = msj.encode().replace(b"\xc2", b"")
                connection.write(write_message)
                _logger.info("Write: %s", write_message)
                response = b""
                sal = connection.read(100)
                _logger.info("Read: %s", sal)
                response = (
                    response.replace(b"\x1c", b"\x7c")
                    .replace(b"\x02", b"\x7c")
                    .replace(b"\x03", b"\x7c")
                    .decode("latin-1")
                )
                if response.startswith("|08|"):
                    return True
                return False
        except serial.serialutil.SerialTimeoutException:
            _logger.info("Serial timeout")
            return False

        except serial.SerialException:
            _logger.info("Serial exception")
            return False
        except Exception:
            _logger.exception("Error while probing %s with protocol %s" % (device, protocol.name))
            return False

    def _set_name(self):
        name = "Desconocido - Pnp Fiscal Printer"
        try:
            with serial_connection(self.device_identifier, self._protocol) as connection:
                response = _send_to_pnp("\x80", connection).decode("latin-1")
                response_splitted = response.split("|")
                name = response_splitted[4] + " - Fiscal Printer PnP"
        except Exception as e:
            _logger.exception(e)

        self.device_name = name

    def _test(self):
        _send_to_pnp("H", self._connection)
        _send_to_pnp("I|Binaural Test", self._connection)
        _send_to_pnp("J", self._connection)
        return {"valid": True, "msg": "Test exitoso"}

    def _print_report_x(self):
        _send_to_pnp("9|X", self._connection)
        return {
            "valid": True,
            "msg": "Reporte X",
        }

    def _print_report_z(self):
        response = _send_to_pnp("8|N", self._connection).decode("latin-1")
        machine_cmd = _send_to_pnp("\x80", self._connection).decode("latin-1")
        response_splitted = machine_cmd.split("|")
        serial_machine = str(response_splitted[4])
        _send_to_pnp("9|Z", self._connection)
        return {
            "valid": True,
            "message": "Reporte Z",
            "data": {
                "_registeredMachineNumber": serial_machine,
                "_dailyClosureCounter": response.split("|")[13],
            },
        }

    def sent_to_pnp(self, data):
        _logger.info(data)
        # read = _send_to_pnp(data, self._connection)
        return data

    def _print_invoice(self, invoice, move_type):
        valid = True
        cmd = []

        max_amount_int = 6
        max_amount_decimal = 2
        max_qty_int = 4
        max_qty_decimal = 3
        max_payment_amount_decimal = 2

        try:
            partner_cmd = f"@|{invoice['partner_id']['name']}|{invoice['partner_id']['vat']}"
            if move_type == "out_refund":
                partner_cmd += f"|{invoice['invoice_affected']['number']}|"
                partner_cmd += f"{invoice['invoice_affected']['serial_machine']}|"
                partner_cmd += f"{invoice['invoice_affected']['date'][:10]}|{invoice['invoice_affected']['date'][11:19]}|D"

            cmd.append(partner_cmd)

            if invoice["partner_id"]["address"]:
                cmd.append(f"A|Direccion {invoice['partner_id']['address']}")
            if invoice["partner_id"]["phone"]:
                cmd.append(f"A|Telefono {invoice['partner_id']['phone']}")

            if len(invoice.get("info", [])) > 0:
                for info in invoice.get("info"):
                    cmd.append(f"A|{info}")

            for item in invoice["invoice_lines"]:
                amount_i, amount_d = split_amount(
                    abs(round(item["price_unit"], max_amount_decimal)),
                    dec=max_amount_decimal,
                )
                qty_i, qty_d = split_amount(item["quantity"], dec=max_qty_decimal)

                cmd.append(
                    str(
                        "B|"
                        + str(item["name"][0:20])
                        + "|"
                        + qty_i.zfill(max_qty_int)
                        + qty_d.zfill(max_qty_decimal)
                        + "|"
                        + amount_i.zfill(max_amount_int)
                        + amount_d.zfill(max_amount_decimal)
                        + "|"
                        + str(TAX.get(str(item["tax"])))
                        + "|"
                        + "M"
                    )
                )

            cmd.append(str("C"))  # sub total en factura

            def is_igtf(payment):
                payment_method = int(payment["payment_method"])
                if payment_method >= 20 and payment_method <= 24:
                    return True
                return False

            if len(invoice["payment_lines"]) <= 1:
                if is_igtf(invoice["payment_lines"][0]):
                    cmd.append("E|U")
                else:
                    cmd.append("E|T")
            else:
                for item in invoice["payment_lines"]:
                    if is_igtf(item):
                        amount_i, amount_d = split_amount(
                            abs(round(item["amount"], max_payment_amount_decimal)),
                            dec=max_payment_amount_decimal,
                        )
                        cmd.append(
                            "E|B|" + amount_i.zfill(1) + amount_d.zfill(max_payment_amount_decimal)
                        )
                    else:
                        cmd.append(f"E|A")

            cmd_to_pnp = "|".join([c.replace(":", "-").replace("|", ":") for c in cmd])

            invoice = ""

            for c in cmd:
                response = _send_to_pnp(c + "|", self._connection)
                if c == cmd[-1]:
                    if move_type == "out_invoice":
                        invoice = response.decode("latin-1").split("|")[5]
                    if move_type == "out_refund":
                        invoice = response.decode("latin-1").split("|")[6]

            machine_cmd = _send_to_pnp("\x80", self._connection).decode("latin-1")
            response_splitted = machine_cmd.split("|")
            serial_machine = str(response_splitted[4])

            msg = "Factura impresa correctamente"
            machine = {
                "valid": True,
                "data": {"sequence": invoice, "serial_machine": serial_machine, "cmd": cmd_to_pnp},
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


def _wrap_low_level_message_around(linea):
    previo = chr(0x02) + chr(0x30) + linea.replace("|", chr(0x1C)) + chr(0x03)
    previo = previo + "AAAA"
    return previo


def _send_to_pnp(cmd, connection):
    try:
        connection.reset_output_buffer()
        connection.reset_input_buffer()

        msj = _wrap_low_level_message_around(cmd)
        write_message = msj.encode().replace(b"\xc2", b"")

        connection.write(write_message)
        _logger.info("Write: %s", write_message)

        i = 0
        rt = b""
        while i < 10:
            sal = connection.read(100)
            _logger.info("Read: %s", sal)
            rt += sal
            i += 1
            if b"\x03" in rt:
                i = 20
        rt = rt.replace(b"\x1c", b"\x7c").replace(b"\x02", b"\x7c").replace(b"\x03", b"\x7c")
    except serial.SerialException:
        rt = False
    return rt


def split_amount(amount, dec=2):
    txt = "{price:.2f}"
    if dec == 3:
        txt = "{price:.3f}"
    if dec == 4:
        txt = "{price:.4f}"
    amount_str = txt.format(price=amount)
    amounts = str(amount_str).split(".")
    return amounts[0], amounts[1]
