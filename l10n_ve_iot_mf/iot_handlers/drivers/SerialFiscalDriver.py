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
import json

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
                return event

        # Wait for new event
        if req["event"].wait(50):
            req["event"].clear()
            req["result"]["session_id"] = req["session_id"]
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
        # Intenta importar el paquete para verificar si ya está instalado
        __import__(package_name)
        print(f"'{package_name}' ya está instalado.")
    except ImportError:
        print(f"'{package_name}' no está instalado. Instalando...")
        # Instala el paquete usando pip
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "--user"])
        except subprocess.CalledProcessError as e:
            print(f"Error al instalar el paquete: {e}")

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
        self.connect(identifier)
        self._connection = None
        self._set_actions()
         
        
        self._set_name()

    @classmethod
    def supported(cls, device):
        try:           
            _logger.info("DLL cargada exitosamente y Tfhka inicializado, linea 108.")            
            condition = False
            
            try:
                dll_path = file_path(f"hw_drivers/iot_handlers/lib/TfhkaNet.dll")
                if not os.path.exists(dll_path):
                    _logger.error(
                        "DLL no encontrada en la ruta especificada: %s", dll_path
                    )
                    return False

                clr.AddReference(dll_path)  # Cargar la DLL
                from TfhkaNet.IF.VE import Tfhka  # Importa la clase desde la DLL

                device_manager = Tfhka()
                # Tfhka = device_manager
                _logger.info("DLL cargada exitosamente y Tfhka inicializado, linea 108.")
            except Exception as e:
                _logger.error("Error al cargar la DLL: %s", e)
                _logger.error(f"Problema del la clase Tfhka: {Tfhka}")


            if platform.system() == "Windows":
                
                _logger.info(f"Verificando en Linux - Identificador del dispositivo: {device['identifier']}")
                
                device_manager.CloseFpCtrl()
                condition = device_manager.OpenFpCtrl(device["identifier"])
                check = device_manager.CheckFPrinter()

            elif platform.system() == "Linux":
                
                _logger.info(f"Verificando en Linux - Identificador del dispositivo: {device['identifier']}")
                
                condition = device["identifier"].__contains__(DEVICE_NAME) or device[
                    "identifier"
                ].__contains__(DEVICE_SHORT_NAME)
                
                _logger.info(f"Resultado de condition: {condition}")

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
            _logger.error(f"No se encontró la DLL en la ruta: {self.dll_path}, linea 255")

        clr.AddReference("TfhkaNet")
        from TfhkaNet.IF.VE import Tfhka
        self.tfhka = Tfhka()  # Aquí se inicializa self.tfhka correctamente.
        _logger.info("DLL TfhkaNet cargada correctamente, linea 260.")
        
    def connect(self, port):
        """
        Establece conexión con la impresora fiscal.
        """
        if not self.tfhka.OpenFpCtrl(port):
            _logger.error(f"No se pudo abrir el puerto: {port}")
        self.port = port
        _logger.info(f"Conexión exitosa al puerto {port}")
    
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
                "report_x": self.print_x_report,
                "report_z": self.PrintZReport,
                "get_last_invoice_number": self.get_last_invoice_number,
                "get_last_out_refund_number": self.get_last_out_refund_number,
                "configure_device": self.configure_device,
                "pre_invoice": self.pre_invoice,
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
        """Establish a connection with the device if needed and have it perform a specific action.

        :param data: the _actions key mapped to the action method we want to call
        :type data: string
        """
                
        if self.tfhka.CheckFPrinter():
            result = self._do_action(data)
        
        else:
            with serial_connection(self.identifier, self._protocol) as connection:
                self._connection = connection
                self._do_action(data)
        
        return {
            "jsonrpc": "2.0",
            "id": None,
            "result": result
        }

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
        """Establece el nombre del dispositivo basado en la información del modelo, país de la impresora y número de registro de la impresora fiscal."""
        try:
            if not self.tfhka:
                _logger.error("El objeto tfhka no está inicializado.")
                
            elif not self.tfhka.CheckFPrinter():
                _logger.error("No hay impresora conectada.")
            else:
                _logger.error("El objeto e=si existe.")
                
            sv_data = self.tfhka.GetSVPrinterData()
            
            if sv_data:
                model = getattr(sv_data, "Model", "Modelo desconocido")
                country = getattr(sv_data, "Country", "País desconocido")
            else:
                model = "Modelo desconocido"
                country = "País desconocido"
            
            estado_s1 = self.get_s1_printer_data()  
            
            if estado_s1:
                machine_number = estado_s1.RegisteredMachineNumber 
                self.device_name = f"Impresora TFHKA: {model} - {country} - {machine_number}"
            else:
                self.device_name = f"Impresora TFHKA: {model} - {country} - Registro desconocido"

            self.device_manufacturer = "The Factory HKA"

            _logger.info(f" Nombre del dispositivo establecido: {self.device_name}")
        
        except Exception as e:
            _logger.error(f"Error al establecer el nombre del dispositivo: {e}")
            self.device_name = "Desconocido - Impresora Fiscal HKAs"

    # def test(self, data):
    #     self.SendCmd("7")
    #     self.SendCmd("800")
    #     self.SendCmd("80$Binaural Test")
    #     self.SendCmd("80!Documento de pruebas")
    #     self.SendCmd("810")
    #     self.data["value"] = {"status": "true"}
    #     event_manager.device_changed(self)
           
    def test(self, data):
        try:
            self.send_command("7")
            self.send_command("800")
            self.send_command("80$Binaural Test")
            self.send_command("80!Documento de pruebas")
            self.send_command("810")
            self.data["value"] = {"status": "true"}
            event_manager.device_changed(self)
            _logger.info(" Test command executed successfully.")
            
            self.get_z_number(data)
        except Exception as e:
            _logger.info("Test command executed successfully.")
            _logger.error(f"Error executing test command: {e}")
            raise
  
    def send_command(self, command):
        """
        Envía un comando a la impresora fiscal.
        """
        try:
            result = self.tfhka.SendCmd(command)
            _logger.info(f"Comando '{command}' enviado con éxito: {result}")
            return result
        except Exception as e:
            _logger.error(f"Error al enviar el comando '{command}': {e}")
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
                _logger.info(f"Cierre: {z_counter}")
                return {"valid": True, "data": {"report_z": z_counter}}
            else:
                return {"valid": False, "message": "No se pudo obtener el número de la última factura Z."}
        except Exception as e:
            _logger.error(f"Error al obtener el número de la última factura Z: {e}")
            return {"valid": False, "message": str(e)}
        
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
        """Procesa e imprime la factura."""
        
        self.data = {"value": {"valid": False, "message": "No se ha completado"}}
        
        retorno = self._validate_invoice_parameter(invoice)
        
        if not retorno.get("valid", False):
            self.data["value"] = retorno
        else:

            self.data["value"] = self.prepare_invoice_data(invoice)  
            
            if self.data["value"].get("valid"):
                send_result = self.send_invoice_commands(self.data["value"])
                result = self.finalize_invoice(True)
                        
        event_manager.device_changed(self)
        
        return result

    def format_invoice_line(self, item, max_amount_decimal, max_qty_decimal, max_amount_int, max_qty_int):
        """Formatea una línea de la factura."""
        
        tax_map = {"0": "0", "1": "!", "2": '"', "3": "#"}
        tax_value = tax_map.get(str(item.get("tax", "")), "")
        
        # Manejo de descuento (precio negativo)
        price_unit = item.get("price_unit", 0)
        if price_unit < 0:
            return None, abs(price_unit)
        
        code = f'|{item["defaul_code"]}|' if item.get("defaul_code") else ""
        
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
        """Agrupa los pagos por método y suma los montos."""

        grouped_payments = defaultdict(float)
        for payment in payment_lines:
            grouped_payments[payment["payment_method"]] += payment["amount"]
        return [{"payment_method": method, "amount": abs(amount)} for method, amount in grouped_payments.items()]

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

            cmd.append(f"iR*{invoice_data['partner_id']['vat']}")
            cmd.append(f"iS*{invoice_data['partner_id']['name']}")
            
            if invoice_data["partner_id"]["address"]:
                cmd.append(str("i00Direccion:" + invoice_data["partner_id"]["address"]))
            if invoice_data["partner_id"]["phone"]:
                cmd.append(str("i01Telefono:" + invoice_data["partner_id"]["phone"]))
                
            if len(invoice_data.get("info", [])) > 0:
                for index, info in enumerate(invoice_data.get("info")):
                    cmd.append(f"i{str(index + 2).zfill(2)}{info}")

            discount = 0
            
            for item in invoice_data["invoice_lines"]:
                line_cmd, line_discount = self.format_invoice_line(
                    item, max_amount_decimal, max_qty_decimal, max_amount_int, max_qty_int
                )
                
                cmd.append(line_cmd)            
            
            cmd.append("3")
            
            payment_lines = self.group_payments(invoice_data["payment_lines"])
 
            for item in payment_lines:
                if item["amount"] > 0 and item["payment_method"] != "01":
                    
                    amount_i, amount_d = self.split_amount(item["amount"], dec=max_payment_amount_decimal)
                    amount_i_filled = amount_i.zfill(max_payment_amount_int)
                    
                    payment_command = str(
                        "2"
                        + str(item["payment_method"])
                        + str(amount_i_filled)
                        + str(amount_d)
                    )
                    cmd.append(payment_command)
                else:
                    continue
            
            if invoice_data.get("has_cashbox", False):
                cmd.append("w")
            
            cmd.append(str("101"))
            
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
            _logger.error(f"Error al preparar los datos de la factura: {_e}")
            return {"valid": False, "message": str(_e)}
        
    def send_invoice_commands(self, cmd):
        """
        Envía los comandos de la factura a la impresora.
        :param cmd: Lista de comandos a enviar.
        :return: Resultado de la operación.
        """
        try:
            _logger.info("cmd 894")
            msg = []
            cmd = cmd.get("cmd", cmd)
        
            for command in cmd:
                
                result = self.tfhka.SendCmd(command)
                
                if not result:
                    msg.append(f"Fallo al enviar comando: {command}")
                    return {"valid": False, "message": msg}

            self.data["value"] = {"valid": True, "msg": msg, "continue": True}
            event_manager.device_changed(self)
            
            return self.data["value"]

        except Exception as _e:
            _logger.error(f"Error al enviar los comandos de la factura: {_e}")
            return {"valid": False, "message": str(_e)}
        
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
            
            result = {
                "valid": True,
                "data": {
                    "sequence": number,
                    "serial_machine": machine_number,
                    "mf_reportz": number_z
                },
                "message": msg
            }
            event_manager.device_changed(self)
            return {
                    "id": None,
                    "jsonrpc": "2.0",
                    "result": result
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
            _logger.info(f"Estado de la impresora: {status.PrinterStatusDescription}")
            return status
        except Exception as e:
            _logger.error(f"Error al obtener estado de la impresora: {e}")
            raise
    
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
    
    def formatear_monto(self, monto):
        parte_entera, parte_decimal = f"{monto:.2f}".split('.')
        monto_sin_punto = parte_entera + parte_decimal
        monto_formateado = monto_sin_punto.zfill(10)
        
        return monto_formateado
    
    def formatear_quantity(self, quantity):
        if '.' in str(quantity):
            parte_entera, parte_decimal = f"{quantity}".split('.')
            quantity_formateado = parte_entera.zfill(5)
            quantity_formateado_2 = parte_decimal.zfill(3)
        else:
            quantity_formateado = str(quantity).zfill(5)
            quantity_formateado_2 = '000'

        return quantity_formateado + quantity_formateado_2
    
    
    def _print_out_refund(self, invoice):
        """
        Imprime una nota de crédito utilizando los datos proporcionados.
        :param invoice: Diccionario con los datos de la nota de crédito.
        """
        try:
            
            number_invoice_affected = invoice.get('invoice_affected', {}).get('number', '')
            
            if number_invoice_affected:
                number_invoice = str(number_invoice_affected)
                number_invoice_formateado = number_invoice.zfill(8)
                cmd_number_invoice_affected = f"iF*{number_invoice_formateado}"
            else:
                _logger.error("Fecha de factura afectada no encontrada en la nota de crédito.")
                return {"valid": False, "message": "No se encontró la fecha de la factura afectada."}
                        
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

            if name_partnet:
                cmd_name = f"iS*{name_partnet}"
            else:
                return {"valid": False, "message": "No se encontró el serial de la máquina fiscal de la factura afectada."}
            
            aditional_lines = []
                        
            address_partner = invoice.get('partner_id', {}).get('address', '')
            
            if address_partner:
                cmd_address = f"i01Direccion:{address_partner}"
                aditional_lines.append(cmd_address)    
                
            invoice_lines = invoice.get('invoice_lines', [])
            product_lines = []
            
            for line in invoice_lines:
                formated_amount = self.formatear_monto(line['price_unit'])
                formated_quantity = self.formatear_quantity(line['quantity'])
                command = f"d{str(line['tax'])}{formated_amount}{formated_quantity}{line['name']}"
                product_lines.append(command)          
            
            payment_lines = self.group_payments(invoice.get("payment_lines", []))
            payment_commands = []
            for item in payment_lines:
                _logger.info("ITEM : %s", item)
                if item["amount"] > 0 and item["payment_method"] != "01":
                    amount_i, amount_d = self.split_amount(item["amount"], dec=2)  
                    amount_i_filled = amount_i.zfill(10)  
                    payment_command = f"2{item['payment_method']}{amount_i_filled}{amount_d}"
                    payment_commands.append(payment_command)

            cmd2 = [
                    'PH01Encabezado 1',
                    cmd_number_invoice_affected,
                    cmd_fecha, 
                    cmd_serial,
                    cmd_vat,
                    cmd_name
                ] + aditional_lines + product_lines + ['3'] + payment_commands + ['101', '199']
            
            for command in cmd2:
                _logger.info("COMANDO : %s", command)
                result = self.tfhka.SendCmd(command)
                
                if not result:
                    _logger.error(f"Fallo al enviar comando: {command}")
                    
            msg = "Nota de crédito impresa correctamente"
            
            estado_s1 = self.get_s1_printer_data()
            
            if estado_s1:
                number = estado_s1.LastCreditNoteNumber
                machine_number = estado_s1.RegisteredMachineNumber
                number_z = estado_s1.DailyClosureCounter + 1
                
                return {"valid": True, "data": {"sequence": number, "serial_machine": machine_number, "mf_reportz":number_z}, "message": msg}
            
            else:
                return {"valid": False, "message": "No se pudo obtener el número de la última nota de crédito."}

        except Exception as _e:
            _logger.error(f"Error al imprimir la nota de crédito: {_e}")
            return {"valid": False, "message": str(_e)}

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
            mode
            + str(
                data["reprint_range_from"].zfill(7) + data["reprint_range_to"].zfill(7)
            )
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
            mode
            + str(
                data["reprint_range_from"].zfill(7)
                + str(data["reprint_range_to"].zfill(7))
            )
        )
        self.data["value"] = {"valid": True, "message": "MENSAJE"}
        event_manager.device_changed(self)
        return self.data["value"]

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
        
        result = self.tfhka.SendCmd(command)
        
        self.data["value"] = result
        event_manager.device_changed(self)
        return self.data["value"]
    
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
                "data": {"sequence": "10", "serial_machine": machine_number, "number":number, "report_z": number_z},
            }

            self.data["value"] = response
            event_manager.device_changed(self)
            return response
        except Exception as _e:
            _logger.warning("exepcion %s", str(_e))
            return str(_e)
    
    def get_last_invoice_number(self, data):
        try:
            estado_s1 = self.get_s1_printer_data()
            
            if estado_s1:
                machine_number = estado_s1.RegisteredMachineNumber
                number = estado_s1.LastInvoiceNumber
                number_z = estado_s1.DailyClosureCounter + 1
                            
            response = {
                "valid": True,
                "data": {"sequence": "10", "serial_machine": machine_number, "number":number, "report_z": number_z},
                # "data": {"sequence": number, "serial_machine": machine_number},
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
            self.data["value"] = result
            event_manager.device_changed(self)
            
            return result
        
        except Exception as e:
            raise
    
    def programacion(self, data):
        try:
            # Enviar el comando de programación
            result = self.tfhka.SendCmd("D")
            
            if result:
                self.data["value"] = {"valid": True, "message": "Programación impresa correctamente."}
                _logger.info("Programación impresa correctamente.")
            else:
                self.data["value"] = {"valid": False, "message": "Error al imprimir la programación."}
                _logger.error("Error al imprimir la programación.")

            event_manager.device_changed(self)
            return self.data["value"]
        except Exception as e:
            _logger.error(f"Error al enviar el comando de programación: {e}")
            self.data["value"] = {"valid": False, "message": str(e)}
            event_manager.device_changed(self)
            return self.data["value"]

    def _HandleCTSRTS(self):
        return True  
    
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
        try:
            status = self.tfhka.GetPrinterStatus()
            _logger.info(f"Estado de la impresora: {status.PrinterStatusDescription}")
            return status
        except Exception as e:
            _logger.error(f"Error al obtener estado de la impresora: {e}")
            raise      

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
    
    def get_s1_printer_data(self):
        """
        Obtiene los datos del estado S1.
        """
        try:
            data = self.tfhka.GetS1PrinterData()
            _logger.info("Datos del estado S1 obtenidos correctamente. : %s", data)
            return data
        except Exception as e:
            _logger.error(f"Error al obtener los datos S1: {e}")
            raise

    # def GetS1PrinterData(self, data):
    #     self.trama = self._States("S1")
    #     res = S1PrinterData(self.trama)
    #     self.data["value"] = {
    #         "valid": True,
    #         "data": res.__dict__,
    #         "message": "S1 Consultado con exito",
    #     }
    #     event_manager.device_changed(self)
    #     return self.data["value"]
    
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
        try:
            self.tfhka.PrintXReport()
            _logger.info("Reporte X impreso correctamente.")
        except Exception as e:
            _logger.error(f"Error al imprimir el reporte X: {e}")
            raise
    
    def print_x_report(self,data):
        """
        Imprime un reporte X.
        """
        try:
            self.tfhka.PrintXReport()
            _logger.info("Reporte X impreso correctamente.")
        except Exception as e:
            _logger.error(f"Error al imprimir el reporte X: {e}")
            raise    
        
    def PrintZReport(self, data, *items):
        try:
            self.tfhka.PrintZReport()
            _logger.info("Reporte Z impreso correctamente.")
        except Exception as e:
            _logger.error(f"Error al imprimir el reporte Z: {e}")
            raise

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
            "0x62": {
                "msg": "En modo fiscal y en emision de documentos no fiscales",
                "code": "6",
            },
            "0x61": {
                "msg": "En modo fiscal y en emision de documentos fiscales",
                "code": "5",
            },
            "0x60": {"msg": "En modo fiscal y en espera", "code": "4"},
            "0x42": {
                "msg": "En modo prueba y en emision de documentos no fiscales",
                "code": "3",
            },
            "0x41": {
                "msg": "En modo prueba y en emision de documentos fiscales",
                "code": "2",
            },
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
            "0x42": {
                "msg": "Error de indole mecanico en la entrega de papel",
                "code": "2",
            },
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
