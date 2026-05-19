# Part of Odoo. See LICENSE file for full copyright and licensing details.

from serial.tools.list_ports import comports

from odoo.addons.iot_drivers.interface import Interface
from odoo.addons.iot_drivers.tools.system import IS_WINDOWS


class CompatSerialInterface(Interface):
    connection_type = "serial"
    allow_unsupported = True

    def get_devices(self):
        return {
            port.device: {"identifier": port.device}
            for port in comports()
            if IS_WINDOWS or port.device != "/dev/ttyAMA10"
        }


SerialInterface = CompatSerialInterface