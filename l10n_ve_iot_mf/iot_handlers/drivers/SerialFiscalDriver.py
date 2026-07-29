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
import subprocess
from collections import defaultdict
from datetime import datetime
from odoo.exceptions import UserError
# import clr
from odoo import http, _
from odoo.tools.misc import file_path
from odoo.addons.hw_drivers.main import iot_devices
from odoo.addons.hw_drivers.event_manager import event_manager
from odoo.addons.hw_drivers.tools import helpers
from odoo.addons.hw_drivers.controllers.driver import DriverController
from odoo.addons.hw_drivers.iot_handlers.drivers.SerialBaseDriver import (
    SerialDriver,
    SerialProtocol,
    serial_connection,
)

from odoo.http import Response

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
        "/hw_drivers/event",
        type="json",
        auth="none",
        cors="*",
        csrf=False,
        save_session=False,
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

def install_package(package_name):
    try:
        __import__(package_name)
        _logger.info("'%s' ya está instalado.", package_name)
    except ImportError:
        _logger.info("'%s' no está instalado. Instalando...", package_name)
        # Instala el paquete usando pip
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "--user"])
        except subprocess.CalledProcessError as e:
            _logger.error("Error al instalar el paquete: %s", e)

try:
    import clr
except:
    install_package("pythonnet")
    
class SerialFiscalDriver(SerialDriver):
    
    connection_type = "serial"
    priority = 0
    _protocol = FiscalProtocol
    mdepura = False
    ##

    def __init__(self, identifier, device):
        super(SerialFiscalDriver, self).__init__(identifier, device)
        self.device_manufacturer = "HKA"
        self.identifier = identifier
        self.device_type = "fiscal_data_module"
        self.device_connection = "serial"
        self.tfhka = NotImplemented
        self._load_dll()
        self._connection = None
        self._set_actions()
        self._set_name()

    @classmethod
    def supported(cls, device):
        try:
            condition = False
            
            try:
                dll_path = file_path("hw_drivers/iot_handlers/lib/TfhkaNet.dll")
                if not os.path.exists(dll_path):
                    _logger.error(
                        "DLL no encontrada en la ruta especificada: %s", dll_path
                    )
                    return False

                clr.AddReference(dll_path)  # Cargar la DLL
                from TfhkaNet.IF.VE import Tfhka  # Importa la clase desde la DLL

                device_manager = Tfhka()

                _logger.info("DLL cargada exitosamente y Tfhka inicializado")
            except Exception as e:
                _logger.error("Error al cargar la DLL: %s", e)
                _logger.error("Problema de la clase Tfhka: %s", Tfhka)


            if platform.system() == "Windows":
                
                _logger.info("Verificando en Linux - Identificador del dispositivo: %s", device['identifier'])
                
                device_manager.CloseFpCtrl()
                condition = device_manager.OpenFpCtrl(device["identifier"])
                check = device_manager.CheckFPrinter()

            elif platform.system() == "Linux":
                
                _logger.info("Verificando en Linux - Identificador del dispositivo: %s", device['identifier'])
                
                condition = device["identifier"].__contains__(DEVICE_NAME) or device[
                    "identifier"
                ].__contains__(DEVICE_SHORT_NAME)
                
                _logger.info("Resultado de condition: %s", condition)

            if condition and check:
                try:
                    device_manager.CloseFpCtrl()
                    return True

                except Exception:
                    _logger.exception(
                        "Error while probing %s with protocol %s"
                        % (device, cls._protocol.name)
                    )
                return True

            else:
                return False

        except Exception as e:
            _logger.error("Could not reach configured server")
            _logger.error("A error encountered : %s " % e)
            return super().supported(device)

    def _load_dll(self):
        """
        Carga la librería TfhkaNet.dll.
        """
        self.dll_path = file_path(f'hw_drivers/iot_handlers/lib/TfhkaNet.dll')
        if not os.path.exists(self.dll_path):
            _logger.error("No se encontró la DLL en la ruta: %s", self.dll_path)
            return

        try:
            from clr import AddReference
            AddReference('TfhkaNet')
            from TfhkaNet.IF.VE import Tfhka
        except Exception as e:
            _logger.error("Error al cargar la DLL o importar Tfhka: %s", e)
            return

        self.tfhka = Tfhka()
        _logger.info("DLL TfhkaNet cargada correctamente.")
        
    def connect(self, port):
        """
        Establece conexión con la impresora fiscal.
        """
        if not self.tfhka.OpenFpCtrl(port):
            _logger.error("No se pudo abrir el puerto: %s", port)
        self.port = port
        _logger.info("Conexión exitosa al puerto %s", port)
    
    def disconnect(self):
        """Cierra la conexión con la impresora fiscal."""
        try:
            if self.tfhka:
                self.tfhka.CloseFpCtrl()
                _logger.info("Puerto %s cerrado correctamente", self.port)
        except Exception as e:
            _logger.error("Error al cerrar el puerto: %s", e)

    def _set_actions(self):
        self._actions.update(
            {
                "status": self.get_status_machine,
                "status1": self.get_s1_printer_data,
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
                "get_last_out_refund_number": self.get_last_out_refund_number,
                "configure_device": self.configure_device,
                "pre_invoice": self.pre_invoice,
                "print_debit_note": self.print_debit_note,
            }
        )
        
    def _do_action(self, data):
            """Helper function that calls a specific action method on the device.

            :param data: the `_actions` key mapped to the action method we want to call
            :type data: string
            """

            with self._device_lock:
                try:
                    result = self._actions[data['action']](data)
                    time.sleep(self._protocol.commandDelay)
                    
                    return result 
                
                except Exception:
                    msg =(f'An error occurred while performing action "{data}" on "{self.device_name}"')
                    _logger.exception(msg)
                    self._status = {'status': self.STATUS_ERROR, 'message_title': msg, 'message_body': traceback.format_exc()}
                    self._push_status()
                self._status = {'status': self.STATUS_CONNECTED, 'message_title': '', 'message_body': ''}
                self.data['status'] = self._status
        
    def action(self, data):
        """
        Establece conexión, ejecuta la acción y desconecta.
        """
        try:
            self.connect(self.identifier)  # Conecta antes de la acción
            result = self._do_action(data)
        finally:
            self.disconnect()  # Desconecta después de la acción

        return {
            "jsonrpc": "2.0",
            "id": None,
            "result": result
        }

    def run(self):
        self._status["status"] = self.STATUS_CONNECTED
        self._push_status()

    def configure_device(self, data):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            if data["data"].get("flag_21", False):
                self.send_command("PJ21" + data["data"]["flag_21"])
            if data["data"].get("flag_24", False):
                self.send_command("PJ24" + data["data"]["flag_24"])
            if data["data"].get("show_version", False):
                self.send_command("PJ77" + data["data"]["show_version"])
            self.send_command("PJ6300")

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
                "PE17CREDITO 03",
                "PE18CREDITO 04",
                "PE19DIVISA 02",
                "PE20DIVISA 01",
                "PE21ZELLE",
            ]
            for line in payment_methods:
                self.send_command(line)

            self.data["value"] = {"valid": "true"}
            event_manager.device_changed(self)
        except Exception as e:
            _logger.error("Error en configure_device: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(e)}

    def _set_name(self):
        """Establece el nombre del dispositivo basado en la información del modelo, país de la impresora y número de registro de la impresora fiscal."""
        try:
            if not self.tfhka:
                _logger.error("El objeto tfhka no está inicializado.")
                
            elif not self.tfhka.CheckFPrinter():
                _logger.error("No hay impresora conectada.")
            else:
                _logger.error("El objeto e=si existe.")
            
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            sv_data = self.tfhka.GetSVPrinterData()
            
            if sv_data:
                model = getattr(sv_data, "Model", "Modelo desconocido")
                country = getattr(sv_data, "Country", "País desconocido")
            else:
                model = "Modelo desconocido"
                country = "País desconocido"
            
            estado_s1 = status["result"] 
            
            if estado_s1:
                machine_number = estado_s1.RegisteredMachineNumber 
                self.device_name = "Impresora TFHKA: %s - %s - %s", model, country, machine_number
            else:
                self.device_name = "Impresora TFHKA: {model} - {country} - Registro desconocido", 

            self.device_manufacturer = "The Factory HKA"

            _logger.info(" Nombre del dispositivo establecido: %s", self.device_name)
        
        except Exception as e:
            _logger.error("Error al establecer el nombre del dispositivo: %s", e)
            self.device_name = "Desconocido - Impresora Fiscal HKAs"

    def test(self, data):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.send_command("7")
            self.send_command("800")
            self.send_command("80$Binaural Test")
            self.send_command("80!Documento de pruebas")
            self.send_command("810")
            self.data["value"] = {"valid": True, "message": "Test impreso correctamente."}
            event_manager.device_changed(self)
            _logger.info(" Test command executed successfully.")
            
            # self.get_z_number(data)
        except Exception as e:
            _logger.error("Error executing test command: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(e)}

    def send_command(self, command):
        """
        Envía un comando a la impresora fiscal.
        """
        try:
            result = self.tfhka.SendCmd(command)
            _logger.info("Comando '%s' enviado con éxito: %s", command, result)
            return result
        except Exception as e:
            _logger.error("Error al enviar el comando '%s': %s", command, e)
            raise

    def get_z_number(self, data):
        """
        Obtiene el número de la última factura Z.
        """
        try:
            # Obtener el estado S1
            estado_s1 = self.get_s1_printer_data()
            if estado_s1:
                z_counter = estado_s1.DailyClosureCounter
                _logger.info("Cierre: %s", z_counter)
                return {"valid": True, "data": {"report_z": z_counter}}
            else:
                return {"valid": False, "message": "No se pudo obtener el número de la última factura Z."}
        except Exception as e:
            _logger.error("Error al obtener el número de la última factura Z: %s", e)
            return {"valid": False, "message": str(e)}
        
    def logger(self, data):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.send_command(str(data["data"]))
            _logger.info(data["data"])
            self.data["value"] = {"valid": "true"}
            event_manager.device_changed(self)
        except Exception as e:
            _logger.error("Error en logger: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(e)}

    def logger_multi(self, data):
        lines = data.get("data", [])
        for line in lines:
            self.send_command(str(line))
        self.data["value"] = {"valid": True}
        event_manager.device_changed(self)
        
    def print_out_invoice(self, invoice):  
        """Procesa e imprime la factura."""
        
        self.data = {"value": {"valid": False, "message": "No se ha completado"}}
        result = self.data["value"]
        
        retorno = self._validate_invoice_parameter(invoice)
        
        if not retorno.get("valid", False):
            self.data["value"] = retorno
        else:

            self.data["value"] = self.prepare_invoice_data(invoice)  
            
            if self.data["value"].get("valid"):
                send_result = self.send_invoice_commands(self.data["value"])
                if not send_result.get("valid", False):
                    self.data["value"] = send_result
                    event_manager.device_changed(self)
                    return send_result
                
                result = self.finalize_invoice(True)
                self.data["value"] = result

        event_manager.device_changed(self)
        return self.data["value"]

    def format_invoice_line(self, item, max_amount_decimal, max_qty_decimal, max_amount_int, max_qty_int):
        """Formatea una línea de la factura."""
        tax_value = TAX.get(str(item.get("tax", "")), "")
        
        # Manejo de descuento (precio negativo)
        price_unit = item.get("price_unit", 0)
        if price_unit < 0:
            return None, abs(price_unit)
        
        code = f'|{item["default_code"]}|' if item.get("default_code") else ""
        
        amount_i, amount_d = self.split_amount(round(price_unit, max_amount_decimal), max_amount_decimal)
        qty_i, qty_d = self.split_amount(item.get("quantity", 0), max_qty_decimal)
        
        formatted_line = (
            f"{tax_value}"
            f"{amount_i.rjust(max_amount_int, '0')}{amount_d.rjust(max_amount_decimal, '0')}"
            f"{qty_i.rjust(max_qty_int, '0')}{qty_d.rjust(max_qty_decimal, '0')}"
            f"{code}"
            f"{item.get('name', '')[:127].strip().replace('Ñ', 'N').replace('ñ', 'n')}"
        )
        
        return formatted_line, None

    def group_payments(self, payment_lines):
        """Agrupa los pagos por método.
        Retorna dos colecciones:
        - payment_lines: montos positivos agrupados por método (para comandos de pago)
        - change_lines: montos negativos convertidos a positivos agrupados por método (para mostrar como cambio)
        """
        grouped = defaultdict(float)
        for payment in payment_lines:
            grouped[payment.get("payment_method")] += payment.get("amount", 0)

        payment_lines = []
        change_lines = []
        for method, amount in grouped.items():
            if amount > 0:
                payment_lines.append({"payment_method": method, "amount": amount})
            elif amount < 0:
                change_lines.append({"payment_method": method, "amount": abs(amount)})
        return payment_lines, change_lines

    def get_closing_method(self, payment_lines=None, fallback_lines=None, default="01"):
        """Determina el método de cierre usando el mayor monto absoluto.

        Si no hay pagos positivos (caso típico en reembolsos), usa `fallback_lines`
        para respetar el método fiscal configurado en la línea de pago.
        """
        candidates = []

        def collect(lines):
            for line in lines or []:
                method_raw = line.get("payment_method")
                if not method_raw:
                    continue
                amount = abs(line.get("amount", 0) or 0)
                if amount > 0:
                    candidates.append(
                        {
                            "payment_method": str(method_raw).strip().zfill(2),
                            "amount": amount,
                        }
                    )

        collect(payment_lines)
        collect(fallback_lines)

        if not candidates:
            return default

        return max(candidates, key=lambda item: item["amount"])["payment_method"]

    def prepare_invoice_data(self, invoice):
        """
        Prepara los datos de la factura.
        :param invoice: Diccionario con los datos de la factura.
        :return: Diccionario con el resultado de la preparación.
        """
        try:
            cmd = []
            invoice_data = invoice.get("data", {})
            
            if not invoice_data:
                _logger.error("No se encontró 'data' en la factura.")
                return {"valid": False, "message": "No se encontró 'data' en la factura."}
            
            flag_21_config = FLAG_21[invoice_data["flag_21"]]
            max_amount_int, max_amount_decimal = flag_21_config["max_amount_int"], flag_21_config["max_amount_decimal"]
            max_qty_int, max_qty_decimal = flag_21_config["max_qty_int"], flag_21_config["max_qty_decimal"]
            max_payment_amount_int, max_payment_amount_decimal =  flag_21_config["max_payment_amount_int"], flag_21_config["max_payment_amount_decimal"]
            disc_int, disc_decimal =  flag_21_config["disc_int"], flag_21_config["disc_decimal"]

            max_rs = invoice_data.get("max_razon_social", 40) or 40
            partner_name = invoice_data["partner_id"]["name"]
            cmd.append(f"iR*{invoice_data['partner_id']['vat']}")
            cmd.append(f"iS*{partner_name[:max_rs]}")

            next_index = 0
            if len(partner_name) > max_rs:
                chunks = [partner_name[i:i+max_rs] for i in range(max_rs, len(partner_name), max_rs)]
                for chunk in chunks:
                    cmd.append(f"i{next_index:02d}{chunk}")
                    next_index += 1

            if invoice_data["partner_id"]["address"]:
                address = invoice_data["partner_id"]["address"]
                first_line = address[:30]
                cmd.append(f"i{next_index:02d}Direccion:{first_line}")
                next_index += 1
                remaining = address[30:70]
                if remaining:
                    cmd.append(f"i{next_index:02d}{remaining}")
                    next_index += 1

            if invoice_data["partner_id"]["phone"]:
                cmd.append(f"i{next_index:02d}Telefono:{invoice_data['partner_id']['phone']}")
                next_index += 1

            for info in invoice_data.get("info", []):
                cmd.append(f"i{next_index:02d}{info}")
                next_index += 1

            payment_lines, change_lines = self.group_payments(invoice_data["payment_lines"])

            for item in change_lines:
                method_raw = item.get("payment_method")
                method_code = str(method_raw).strip().zfill(2) if method_raw else "--"
                amount_str = "{:.2f}".format(item["amount"])
                cmd.append(f"i{next_index:02d}CAMBIO M{method_code}: {amount_str}")
                next_index += 1

            discount = 0
            
            for item in invoice_data["invoice_lines"]:
                line_cmd, line_discount = self.format_invoice_line(
                    item, max_amount_decimal, max_qty_decimal, max_amount_int, max_qty_int
                )
                
                cmd.append(line_cmd)            
            
            cmd.append("3")
            
            closing_method = self.get_closing_method(
                payment_lines=payment_lines,
                fallback_lines=change_lines,
            )
 
            for item in payment_lines:
                method_raw = item.get("payment_method")
                if not method_raw:
                    return {"valid": False, "message": "Método de pago fiscal no configurado en una línea de pago."}

                method_code = str(method_raw).strip().zfill(2)
                # El método de cierre se envía con comando 1XX, no con 2XX.
                # Enviar en 2XX solo métodos distintos al de cierre.
                if item["amount"] > 0:
                    amount_i, amount_d = self.split_amount(item["amount"], dec=max_payment_amount_decimal)
                    amount_i_filled = amount_i.zfill(max_payment_amount_int)
                    
                    payment_command = str(
                        "2"
                        + method_code
                        + str(amount_i_filled)
                        + str(amount_d)
                    )
                    cmd.append(payment_command)
            
            if invoice_data.get("has_cashbox", False):
                cmd.append("w")
            
            cmd.append(str("1" + closing_method))
            
            if len(invoice_data.get("aditional_lines", [])) > 0:
                for index, aditional_lines in enumerate(invoice_data.get("aditional_lines")):
                    cmd.append(f"i{str(index).zfill(2)}{aditional_lines}")
                                
            cmd.append(str("199"))
            
            self.data["value"] = {"valid": True, "data": cmd}
            
            return {
                "valid": True,
                "cmd": cmd,
                "discount": discount,
                "payment_lines": payment_lines,
            }

        except Exception as _e:
            _logger.error("Error al preparar los datos de la factura: %s", _e)
            return {"valid": False, "message": str(_e)}
        
    def send_invoice_commands(self, cmd):
        """
        Envía los comandos de la factura a la impresora.
        :param cmd: Lista de comandos a enviar.
        :return: Resultado de la operación.
        """
        try:
            msg = []
            cmd = cmd.get("cmd", cmd)

            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            for command in cmd:
                result = self.send_command(command)
                
                if not result and not (command.startswith("1") and len(command) == 3):
                    msg.append(f"Fallo al enviar comando: {command}")
                    self.send_command("199")
                    return {"valid": False, "message": msg}

            self.data["value"] = {"valid": True, "msg": msg, "continue": True}
            
            return self.data["value"]

        except Exception as _e:
            _logger.error("Error al enviar los comandos de la factura: %s", _e)
            return {"valid": False, "message": str(_e), "continue": False}
        
    def finalize_invoice(self, data):
        """
        Finaliza el proceso de impresión y devuelve el resultado.
        :return: Resultado de la operación.
        """
        msg = "Factura impresa correctamente"
        estado_s1 = self.get_s1_printer_data()
        
        if estado_s1:
            number = estado_s1.LastInvoiceNumber
            machine_number = estado_s1.RegisteredMachineNumber
            number_z = estado_s1.DailyClosureCounter + 1
            
            return{
                "valid": True,
                "data": {
                    "sequence": number,
                    "serial_machine": machine_number,
                    "mf_reportz": number_z
                },
                "message": msg
            }
            
        else:
            self.data["value"] = {"valid": False, "message": "No se pudo obtener el número de la última factura."}
            event_manager.device_changed(self)
            
            return self.data["value"]
        
    def get_status(self):
        """
        Obtiene el estado de la impresora.
        """        
        try:
            status = self.tfhka.GetPrinterStatus()
            _logger.info("Estado de la impresora: %s", status.PrinterStatusDescription)
            return status
        except Exception as e:
            _logger.error("Error al obtener estado de la impresora: %s", e)
            msg = _("Error al obtener estado de la impresora: %s")
            raise UserError(msg % e)
    
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
    
    def print_debit_note(self, invoice):
        estado_s1 = self.get_s1_printer_data()
        machine_number = estado_s1.RegisteredMachineNumber
        
        if invoice["data"]["invoice_affected"]["serial_machine"] != machine_number:
            msg = _(
                "¡Error de impresora fiscal! "
                "La impresora fiscal actual no coincide con la usada en la factura original. "
                "Serial de la factura: %(serial_factura)s. "
                "Serial de la impresora conectada: %(serial_impresora)s."
            )
            raise UserError(msg % {
                'serial_factura': invoice['data']['invoice_affected']['serial_machine'],
                'serial_impresora': machine_number,
            })
        
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
            estado_s1 = self.get_s1_printer_data()
            last_number = estado_s1.LastCreditNoteNumber
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            _logger.warning("print_out_refound %s", invoice)
            next_index = 0
            max_rs = invoice.get("max_razon_social", 40) or 40
            partner_name = invoice["partner_id"]["name"]
            cmd.append(str("iR*" + invoice["partner_id"]["vat"]))
            cmd.append(str("iS*" + partner_name[:max_rs]))
            cmd.append(str("iF*" + invoice["invoice_affected"]["number"]))
            cmd.append(str("iI*" + invoice["invoice_affected"]["serial_machine"]))
            cmd.append(str("iD*" + invoice["invoice_affected"]["date"]))

            if len(partner_name) > max_rs:
                chunks = [partner_name[i:i+max_rs] for i in range(max_rs, len(partner_name), max_rs)]
                for chunk in chunks:
                    cmd.append(f"i{next_index:02d}{chunk}")
                    next_index += 1

            if invoice["partner_id"]["address"]:
                address = invoice["partner_id"]["address"]
                first_line = address[:30]
                cmd.append(f"i{next_index:02d}Direccion:{first_line}")
                next_index += 1
                remaining = address[30:70]
                if remaining:
                    cmd.append(f"i{next_index:02d}{remaining}")
                    next_index += 1

            if invoice["partner_id"]["phone"]:
                cmd.append(f"i{next_index:02d}Telefono:{invoice['partner_id']['phone']}")
                next_index += 1

            for info in invoice.get("info", []):
                cmd.append(f"i{next_index:02d}{info}")
                next_index += 1

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

            closing_method = self.get_closing_method(payment_lines=new_payment_lines)

            for item in new_payment_lines:
                method_code = str(item["payment_method"]).strip().zfill(2)
                if item["amount"] > 0 and method_code != closing_method:
                    amount_i, amount_d = self.split_amount(
                        item["amount"],
                        dec=max_payment_amount_decimal,
                    )
                    cmd.append(
                        "2"
                        + method_code
                        + amount_i.zfill(max_payment_amount_int)
                        + amount_d
                    )

            cmd.append(str("1" + closing_method))
            if len(invoice.get("aditional_lines", [])) > 0:
                for index, aditional_lines in enumerate(invoice.get("aditional_lines")):
                    cmd.append(f"i{str(index).zfill(2)}{aditional_lines}")
            cmd.append(str("199"))

            for command in cmd:
                self.send_command(command)

            msg = "Nota de debito impresa correctamente"
            res = self.get_s1_printer_data()

            number = res.LastDebitNoteNumber
            number_z = res.DailyClosureCounter
            machine_number = res.RegisteredMachineNumber
            
            
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

    def format_refund_line(self, item, max_amount_int, max_amount_decimal, max_qty_int, max_qty_decimal):
        """
        Formatea una línea de nota de crédito (refund) para impresión fiscal.
        """
        TAX = {}

        price_unit = item.get("price_unit", 0)
        if price_unit < 0:
            return None, abs(price_unit)

        code = f'|{item["default_code"]}|' if item.get("default_code") else ""

        tax_code = str(item.get("tax", ""))
        tax_value = TAX.get(tax_code, tax_code)

        amount_i, amount_d = self.split_amount(round(price_unit, max_amount_decimal), max_amount_decimal)
        qty_i, qty_d = self.split_amount(item.get("quantity", 0), max_qty_decimal)

        formatted_line = (
            f"d{tax_value}"
            f"{amount_i.rjust(max_amount_int, '0')}{amount_d.rjust(max_amount_decimal, '0')}"
            f"{qty_i.rjust(max_qty_int, '0')}{qty_d.rjust(max_qty_decimal, '0')}"
            f"{code}"
            f"{item.get('name', '')[:127].strip().replace('Ñ', 'N').replace('ñ', 'n')}"
        )
        return formatted_line, None

    def _print_out_refund(self, invoice):
        """
        Prints a credit note using the provided data.
        :param invoice: Dictionary containing the credit note data.
        """
        try:
            max_amount_int = FLAG_21[invoice["flag_21"]]["max_amount_int"]
            max_amount_decimal = FLAG_21[invoice["flag_21"]]["max_amount_decimal"]
            max_payment_amount_int = FLAG_21[invoice["flag_21"]]["max_payment_amount_int"]
            max_payment_amount_decimal = FLAG_21[invoice["flag_21"]]["max_payment_amount_decimal"]
            max_qty_int = FLAG_21[invoice["flag_21"]]["max_qty_int"]
            max_qty_decimal = FLAG_21[invoice["flag_21"]]["max_qty_decimal"]
            disc_int = FLAG_21[invoice["flag_21"]]["disc_int"]
            disc_decimal = FLAG_21[invoice["flag_21"]]["disc_decimal"]

            number_invoice_affected = invoice.get('invoice_affected', {}).get('number', '')
            
            if number_invoice_affected:
                number_invoice = str(number_invoice_affected)
                number_invoice_formateado = number_invoice.zfill(8)
                cmd_number_invoice_affected = f"iF*{number_invoice_formateado}"
            else:
                _logger.error("Numero de factura afectada no encontrada en la nota de crédito.")
                return {"valid": False, "message": "No se encontró el numero de la factura afectada."}
                        
            fecha_afectada = invoice.get('invoice_affected', {}).get('date', '')
            
            if fecha_afectada:
                fecha_validada = datetime.strptime(fecha_afectada, "%d/%m/%Y").strftime("%d/%m/%Y")
                cmd_fecha = f"iD*{fecha_validada}"
            else:
                _logger.error("Fecha de factura afectada no encontrada en la nota de crédito.")
                return {"valid": False, "message": "No se encontró la fecha de la factura afectada."}
            
            serial_machine = invoice.get('invoice_affected', {}).get('serial_machine', '')

            if serial_machine:
                cmd_serial = f"iI*{serial_machine}"
            else:
                _logger.error("Serial de la máquina fiscal no encontrado en la factura afectada.")
                return {"valid": False, "message": "No se encontró el serial de la máquina fiscal de la factura afectada."}
            
            document_partnet = invoice.get('partner_id', {}).get('vat', '')

            if document_partnet:
                cmd_vat = f"iR*{document_partnet}"
            else:
                return {"valid": False, "message": "No se encontró el serial de la máquina fiscal de la factura afectada."}
            
            name_partnet = invoice.get('partner_id', {}).get('name', '')

            if not name_partnet:
                return {"valid": False, "message": "No se encontró la razón social del cliente en la factura afectada."}

            aditional_lines = []
            next_index = 0
            max_rs = invoice.get("max_razon_social", 40) or 40
            cmd_name = f"iS*{name_partnet[:max_rs]}"

            if len(name_partnet) > max_rs:
                chunks = [name_partnet[i:i+max_rs] for i in range(max_rs, len(name_partnet), max_rs)]
                for chunk in chunks:
                    aditional_lines.append(f"i{next_index:02d}{chunk}")
                    next_index += 1

            address_partner = invoice.get('partner_id', {}).get('address', '')
            if address_partner:
                first_line = address_partner[:30]
                aditional_lines.append(f"i{next_index:02d}Direccion:{first_line}")
                next_index += 1
                remaining = address_partner[30:70]
                if remaining:
                    aditional_lines.append(f"i{next_index:02d}{remaining}")
                    next_index += 1

            phone_partner = invoice.get('partner_id', {}).get('phone', '')
            if phone_partner:
                aditional_lines.append(f"i{next_index:02d}Telefono:{phone_partner}")
                next_index += 1

            for info in invoice.get("info", []):
                aditional_lines.append(f"i{next_index:02d}{info}")
                next_index += 1

            invoice_lines = invoice.get('invoice_lines', [])
            product_lines = []
            for line in invoice_lines:
                formatted_line, discount = self.format_refund_line(
                    line,
                    max_amount_int,
                    max_amount_decimal,
                    max_qty_int,
                    max_qty_decimal
                )
                if formatted_line:
                    product_lines.append(formatted_line)          

            payment_lines, change_lines = self.group_payments(invoice.get("payment_lines", []))
            payment_commands = []
            
            closing_method = self.get_closing_method(
                payment_lines=payment_lines,
                fallback_lines=change_lines,
            )

            # En NC, si no hay pagos positivos (caso común), usar change_lines
            # para conservar métodos mixtos en comandos fiscales.
            payment_lines_to_send = payment_lines or change_lines

            for item in payment_lines_to_send:
                _logger.info("ITEM : %s", item)
                method_code = str(item["payment_method"]).strip().zfill(2)
                if item["amount"] > 0 and method_code != closing_method:
                    amount_i, amount_d = self.split_amount(item["amount"], dec=max_payment_amount_decimal)
                    amount_i_filled = amount_i.zfill(max_payment_amount_int)
                    payment_command = f"2{method_code}{amount_i_filled}{amount_d}"
                    payment_commands.append(payment_command)

            cmd2 = [
                    'PH01Encabezado 1',
                    cmd_number_invoice_affected,
                    cmd_fecha, 
                    cmd_serial,
                    cmd_vat,
                    cmd_name
                ] + aditional_lines + product_lines + ['3'] + payment_commands + [str("1" + closing_method), '199']
            
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            for command in cmd2:
                result = self.send_command(command) 
                
                if not result:
                    _logger.error("Fallo al enviar comando: %s", command)

            estado_s1 = self.get_s1_printer_data()
            
            if estado_s1:
                number = estado_s1.LastCreditNoteNumber
                machine_number = estado_s1.RegisteredMachineNumber
                number_z = estado_s1.DailyClosureCounter + 1
                return {
                    "valid": True,
                    "data": {"sequence": number, "serial_machine": machine_number, "mf_reportz": number_z},
                    "message": "Nota de crédito impresa correctamente"
                }
            else:
                return {"valid": False, "message": "No se pudo obtener el número de la última nota de crédito."}

        except Exception as _e:
            _logger.error("Error al imprimir la nota de crédito: %s", _e)
            return {"valid": False, "message": str(_e)}

    def print_resume(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.send_command("I2S" + str(data["resume_range_from"] + data["resume_range_to"]))
            self.data["value"] = {"valid": True, "message": "MENSAJE"}
            event_manager.device_changed(self)
            return self.data["value"]
        except Exception as _e:
            _logger.error("Error al imprimir el resumen: %s", _e)
            self.data["value"] = {"valid": False, "message": str(_e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(_e)}

    def reprint_date(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        _logger.info(data)
        mode = data.get("mode", "Rs")
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.send_command(
                mode
                + str(
                    data["reprint_range_from"].zfill(7) + data["reprint_range_to"].zfill(7)
                )
            )
            self.data["value"] = {"valid": True, "message": "MENSAJE"}
            event_manager.device_changed(self)
            return self.data["value"]
        except Exception as _e:
            _logger.error("Error al imprimir la reimpresión por fecha: %s", _e)
            self.data["value"] = {"valid": False, "message": str(_e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(_e)}

    def reprint_type(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        _data = data.get("data", False)
        if _data:
            data = _data
        _logger.info(data)
        mode = data.get("mode", "R@")
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.send_command(
                mode
                + str(
                    data["reprint_range_from"].zfill(7)
                    + str(data["reprint_range_to"].zfill(7))
                )
            )
            self.data["value"] = {"valid": True, "message": "MENSAJE"}
            event_manager.device_changed(self)
            return self.data["value"]
        except Exception as _e:
            _logger.error("Error al imprimir la reimpresión por tipo: %s", _e)
            self.data["value"] = {"valid": False, "message": str(_e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(_e)}

    def reprint(self, data):
        self.data["value"] = {"valid": False, "message": "No se ha completado"}
        
        data = data.get("data") or data
            
        mode = ""
        if data["type"] == "out_invoice":
            mode = "RF"
        if data["type"] == "out_refund":
            mode = "RC"
        if mode == "":
            self.data["value"] = {"valid": False, "message": "Datos no validos"}
            event_manager.device_changed(self)
            return self.data["value"]
        
        command = mode + str(data["mf_number"].zfill(7) + str(data["mf_number"].zfill(7)))
        
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            result = self.send_command(command)
            
            self.data["value"] = {"valid": result}
            event_manager.device_changed(self)
            return{"valid": result}
        except Exception as _e:
            _logger.error("Error al imprimir la reimpresión: %s", _e)
            self.data["value"] = {"valid": False, "message": str(_e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(_e)}

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
            estado_s1 = self.get_s1_printer_data()

            machine_number = estado_s1.RegisteredMachineNumber
            number = estado_s1.LastCreditNoteNumber
            number_z = estado_s1.DailyClosureCounter + 1
            
            response = {
                "valid": True,
                "data": {"sequence": number, "serial_machine": machine_number, "number":number, "report_z": number_z},
            }

            self.data["value"] = response
            event_manager.device_changed(self)
            return response
        except Exception as _e:
            _logger.warning("exepcion %s", str(_e))
            return str(_e)

    def get_last_invoice_number(self, data):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            estado_s1 = status["result"]
            
            if estado_s1:
                machine_number = estado_s1.RegisteredMachineNumber
                number = estado_s1.LastInvoiceNumber
                number_z = estado_s1.DailyClosureCounter + 1
                            
            response = {
                "valid": True,
                "data": {"sequence": number, "serial_machine": machine_number, "number":number, "report_z": number_z},
            }

            self.data["value"] = response
            event_manager.device_changed(self)
            return response
        except Exception as _e:
            _logger.warning("exepcion %s", str(_e))
            self.data["value"] = {"valid": False, "message": str(_e)}
            event_manager.device_changed(self)
            return self.data["value"]

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
        
        if (
            not "number" in invoice_affected
            or invoice["invoice_affected"]["number"] == ""
        ):
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

    def _validate_invoice_parameter(self, invoice):
        try:        
            msg = []
            valid = True

            if not invoice:
                msg.append("No se recibió información de la factura")
                return False, msg

            invoice_data = invoice.get("data", {})
            if not invoice_data:
                msg.append("No se encontró 'data' en la factura")
                return {"valid": False, "message": msg}            
            
            required_fields = {
                "company_id": "No se encontró la empresa",
                "partner_id": "No se recibió información del cliente",
                "invoice_lines": "No se recibió información de los productos",
                "payment_lines": "No se recibió información de los pagos"
            }
            
            for field, error_msg in required_fields.items():
                if not invoice_data.get(field):
                    msg.append(error_msg)
                    valid = False

            partner = invoice_data.get("partner_id", {})
            partner_required = {
                "vat": "El cliente no tiene cédula",
                "name": "El cliente no tiene nombre"
            }
            
            for field, error_msg in partner_required.items():
                if not partner.get(field):
                    msg.append(error_msg)
                    valid = False
            
            for line in invoice_data.get("invoice_lines", []):
                line_required = {
                    "price_unit": "No se encontró el precio del producto",
                    "quantity": "No se encontró la cantidad del producto",
                    "tax": "El impuesto no es válido",
                    "name": "No se encontró el nombre del producto"
                }            
                

            for field, error_msg in line_required.items():
                if field not in line:
                    msg.append(error_msg)
                    valid = False
                elif field == "tax":
                    try:
                        tax_value = int(line["tax"])
                        if not (0 <= tax_value <= 4):
                            msg.append(error_msg)
                            valid = False
                    except (ValueError, TypeError):
                        msg.append("El impuesto no es un número válido")
                        valid = False
            
            for line in invoice_data.get("payment_lines", []):
                if "amount" not in line:
                    msg.append("No se recibió el monto del pago")
                    valid = False

                if "payment_method" not in line:
                    msg.append("El método de pago no es aceptado o no se recibió")
                    valid = False
                else:
                    try:
                        payment_method = int(line["payment_method"])
                        if not (1 <= payment_method <= 24):
                            msg.append("El método de pago no es aceptado o no se recibió")
                            valid = False
                    except (ValueError, TypeError):
                        msg.append("El método de pago no es un número válido")
                        valid = False
            
            result = {"valid": valid, "message": msg}
            
            return result
        
        except Exception as e:
            msg = _("Error al validar factura: %s")
            raise UserError(msg % e)
    
    def programacion(self, data):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])

            result = self.send_command("D")
            
            if result:
                self.data["value"] = {"valid": True, "message": "Programación impresa correctamente."}
                _logger.info("Programación impresa correctamente.")
            else:
                self.data["value"] = {"valid": False, "message": "Error al imprimir la programación."}
                _logger.error("Error al imprimir la programación.")

            event_manager.device_changed(self)
            return self.data["value"]
        except Exception as e:
            _logger.error("Error al enviar el comando de programación: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
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
                self.send_command(linea)

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
            else:
                break
        return None

    def get_status_machine(self, data):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            status = status["status"]
            _logger.info("Estado de la impresora: %s", status.PrinterStatusDescription)
            self.data["value"] = {"valid": True, "message": "Estado de la impresora: " + status.PrinterStatusDescription}
            event_manager.device_changed(self)

            return status
        except Exception as e:
            _logger.error("Error al obtener estado de la impresora: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(e)}

    def ReadFpStatus(self, data):
        try:

            result = self.get_s1_printer_data()
            if result:
                status_obj = self.tfhka.GetPrinterStatus()

                status = self._GetStatusError(status_obj.PrinterStatusCode, status_obj.PrinterErrorCode)

                return {
                    "valid": True,
                    "message": f"""
                    {status['status']['code']}: {status['status']['msg']}
                    {status['error']['code']}: {status['error']['msg']}
                    """,
                    "data": status,
                    "status": status_obj,
                    "result": result,
                }
            else:
                status = self._GetStatusError(0, 128)
                return {
                    "valid": False,
                    "message": f"""
                    {status['status']['code']}: {status['status']['msg']}
                    {status['error']['code']}: {status['error']['msg']}
                    """,
                    "data": status,
                    "status": False,
                    "result": False,
                }

        except Exception as e:
            _logger.error("Error al leer estado fiscal: %s", e)
            status = self._GetStatusError(0, 128)
            return {
                "valid": False,
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
    
    def get_s1_printer_data(self):
        """
        Obtiene los datos del estado S1.
        """
        try:
            data = self.tfhka.GetS1PrinterData()
            _logger.info("Datos del estado S1 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S1: %s", e)
            raise

    def GetS2PrinterData(self):
        try:
            data = self.tfhka.GetS2PrinterData()
            _logger.info("Datos del estado S2 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S2: %s", e)
            raise

    def GetS25PrinterData(self):
        try:
            data = self.tfhka.GetS25PrinterData()
            _logger.info("Datos del estado S25 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S25: %s", e)
            raise

    def GetS3PrinterData(self):
        try:
            data = self.tfhka.GetS3PrinterData()
            _logger.info("Datos del estado S3 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S3: %s", e)
            raise

    def GetS4PrinterData(self):
        try:
            data = self.tfhka.GetS4PrinterData()
            _logger.info("Datos del estado S4 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S4: %s", e)
            raise

    def GetS5PrinterData(self):
        try:
            data = self.tfhka.GetS5PrinterData()
            _logger.info("Datos del estado S5 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S5: %s", e)
            raise

    def GetS6PrinterData(self):
        try:
            data = self.tfhka.GetS6PrinterData()
            _logger.info("Datos del estado S6 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S6: %s", e)
            raise

    def GetS7PrinterData(self):
        try:
            data = self.tfhka.GetS7PrinterData()
            _logger.info("Datos del estado S7 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S7: %s", e)
            raise

    def GetS8EPrinterData(self):
        try:
            data = self.tfhka.GetS8EPrinterData()
            _logger.info("Datos del estado S8E obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S8E: %s", e)
            raise

    def GetS8PPrinterData(self):
        try:
            data = self.tfhka.GetS8PPrinterData()
            _logger.info("Datos del estado S8P obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error("Error al obtener los datos S8P: %s", e)
            raise

    def GetXReport(self):
        self.trama = self._UploadDataReport("U0X")
        # print self.trama
        self.XReport = self.tfhka.ReportData(self.trama)
        return self.XReport

    def GetX2Report(self):
        self.trama = self._UploadDataReport("U1X")
        # print self.trama
        self.XReport = self.tfhka.ReportData(self.trama)
        return self.XReport

    def GetX4Report(self):
        self.trama = self._UploadDataReport("U0X4")
        # print self.trama
        self.XReport = self.tfhka.AcumuladosX(self.trama)
        return self.XReport

    def GetX5Report(self):
        self.trama = self._UploadDataReport("U0X5")
        # print self.trama
        self.XReport = self.tfhka.AcumuladosX(self.trama)
        return self.XReport

    def GetX7Report(self):
        self.trama = self._UploadDataReport("U0X7")
        # print self.trama
        self.XReport = self.tfhka.AcumuladosX(self.trama)
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
                self.Z = self.tfhka.ReportData(report)
                self.ReportData.append(self.Z)
                i += 1
        else:
            self.trama = self._UploadDataReport("U0Z")
            self.ReportData = self.tfhka.ReportData(self.trama)
        return self.ReportData
    
    def PrintXReport(self,data):
        """
        Imprime un reporte X.
        """
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.tfhka.PrintXReport()
            _logger.info("Reporte X impreso correctamente.")
            self.data["value"] = {"valid": True, "message": "Reporte X impreso correctamente."}
            event_manager.device_changed(self)
            return {"valid": True, "message": "Reporte X impreso correctamente."}

        except Exception as e:
            _logger.error("Error al imprimir el reporte X: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(e)}
        
    def PrintZReport(self, data, *items):
        try:
            status = self.ReadFpStatus(True)
            if status["data"]["error"]["code"] != "0":
                raise Exception(status["data"]["error"]["msg"])
            if status["data"]["status"]["code"] not in ["1", "4"]:
                raise Exception(status["data"]["status"]["msg"])
            
            self.tfhka.PrintZReport()
            _logger.info("Reporte Z impreso correctamente.")
            self.data["value"] = {"valid": True, "message": "Reporte Z impreso correctamente."}
            event_manager.device_changed(self)
            return {"valid": True, "message": "Reporte Z impreso correctamente."}
        except Exception as e:
            _logger.error("Error al imprimir el reporte Z: %s", e)
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return {"valid": False, "message": str(e)}

    def _GetStatusError(self, st, er):


        status_codes = {
            0:  {"msg": "Estado desconocido.", "code": "0"},
            1:  {"msg": "En modo prueba y en espera.", "code": "1"},
            2:  {"msg": "En modo prueba y emisión de documentos.", "code": "2"},
            3:  {"msg": "En modo prueba y emisión de documentos no fiscales.", "code": "3"},
            4:  {"msg": "En modo fiscal y en espera.", "code": "4"},
            5:  {"msg": "En modo fiscal y emisión de documentos fiscales.", "code": "5"},
            6:  {"msg": "En modo fiscal y emisión de documentos no fiscales.", "code": "6"},
            7:  {"msg": "En modo fiscal, cercana carga completa de la memoria fiscal y en espera.", "code": "7"},
            8:  {"msg": "En modo fiscal, cercana carga completa de la memoria fiscal y en emisión de documentos fiscales.", "code": "8"},
            9:  {"msg": "En modo fiscal, cercana carga completa de la memoria fiscal y en emisión de documentos no fiscales.", "code": "9"},
            10: {"msg": "En modo fiscal, carga completa de la memoria fiscal y en espera.", "code": "10"},
            11: {"msg": "En modo fiscal, carga completa de la memoria fiscal y en emisión de documentos fiscales.", "code": "11"},
            12: {"msg": "En modo fiscal, carga completa de la memoria fiscal y en emisión de documentos no fiscales.", "code": "12"},
        }

        error_codes = {
            0:   {"msg": "No hay error.", "code": "0"},
            1:   {"msg": "Fin en la entrega de papel.", "code": "1"},
            2:   {"msg": "Error de índole mecánico en la entrega de papel.", "code": "2"},
            3:   {"msg": "Fin en la entrega de papel y error mecánico.", "code": "3"},
            80:  {"msg": "Comando inválido o valor inválido.", "code": "80"},
            84:  {"msg": "Tasa inválida.", "code": "84"},
            88:  {"msg": "No hay asignadas directivas.", "code": "88"},
            92:  {"msg": "Comando inválido.", "code": "92"},
            96:  {"msg": "Error fiscal.", "code": "96"},
            100: {"msg": "Error de la memoria fiscal.", "code": "100"},
            108: {"msg": "Memoria fiscal llena.", "code": "108"},
            112: {"msg": "Buffer completo. (debe enviar el comando de reinicio)", "code": "112"},
            128: {"msg": "Error en la comunicación.", "code": "128"},
            137: {"msg": "No hay respuesta.", "code": "137"},
            144: {"msg": "Error LRC.", "code": "144"},
            145: {"msg": "Error interno api.", "code": "145"},
            153: {"msg": "Error en la apertura del archivo.", "code": "153"},
        }

        status = {"msg": "Status Desconocido", "code": "#"}
        error = {"msg": "Error Desconocido", "code": "#"}

        if st in status_codes:
            status = status_codes[st]
        if er in error_codes:
            error = error_codes[er]

        return {"status": status, "error": error}
