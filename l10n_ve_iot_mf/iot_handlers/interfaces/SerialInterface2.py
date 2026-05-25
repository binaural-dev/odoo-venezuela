# Part of Odoo. See LICENSE file for full copyright and licensing details.

import serial.tools.list_ports
import logging
import platform
import urllib3
import json
from odoo.addons.iot_drivers.tools import helpers
from odoo.addons.iot_drivers.main import drivers, interfaces, iot_devices, unsupported_devices

from .serial_interface_compat import CompatSerialInterface

_logger = logging.getLogger(__name__)


class SerialInterface(CompatSerialInterface):
    allow_unsupported = True

    def get_devices(self):
        serial_devices = {}
        try:
            if platform.system() == "Windows":
                server = helpers.get_odoo_server_url()
                unsupported = {device for device in unsupported_devices if device in self}
                urllib3.disable_warnings()
                http = urllib3.PoolManager(cert_reqs="CERT_NONE")
                waiting = http.request(
                    "GET",
                    server + "/iot_blacklist/ports",
                )

                b_body = waiting._body
                body = json.loads(b_body.decode("utf-8"))
                for port in serial.tools.list_ports.comports():
                    
                    # if(port.device in body[helpers.get_identifier()]):
                    #     _logger.warning('ENCONTRE PUERTOS!')
                    #     continue #TODO DESCOMENTAR 

                    serial_devices[port.device] = {
                        'identifier': port.device
                    }
                    _logger.warning("LOS DISPOSITIVOS SOIOON %s", serial_devices)
                return serial_devices

        except Exception as e:
            return super().get_devices()
