# Part of Odoo. See LICENSE file for full copyright and licensing details.

import serial.tools.list_ports
import logging
import platform
import urllib3
import json
from odoo.addons.hw_drivers.iot_handlers.interfaces.SerialInterface import SerialInterface
from odoo.addons.hw_drivers.tools import helpers

_logger = logging.getLogger(__name__)


class SerialInterface(SerialInterface):
    connection_type = 'serial'

    def get_devices(self):
        serial_devices = {}
        try:
            if platform.system() == "Windows":
                server = helpers.get_odoo_server_url()
                urllib3.disable_warnings()
                http = urllib3.PoolManager(cert_reqs="CERT_NONE")
                waiting = http.request(
                    "GET",
                    server + "/iot_blacklist/ports",
                )

                b_body = waiting._body
                body = json.loads(b_body.decode("utf-8"))

                for port in serial.tools.list_ports.comports():
                    if(port.device in body[helpers.get_mac_address()]):
                        continue

                    serial_devices[port.device] = {
                        'identifier': port.device
                    }

                return serial_devices

        except Exception as e:
            return super().get_devices()
