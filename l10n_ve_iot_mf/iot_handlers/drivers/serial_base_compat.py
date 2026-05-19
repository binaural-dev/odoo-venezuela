# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from typing import NamedTuple
import logging
import serial
import time
import traceback
from threading import Lock

from odoo.addons.iot_drivers.driver import Driver
from odoo.addons.iot_drivers.event_manager import event_manager

_logger = logging.getLogger(__name__)


class CompatSerialProtocol(NamedTuple):
    name: any
    baudrate: any
    bytesize: any
    stopbits: any
    parity: any
    timeout: any
    writeTimeout: any
    measureRegexp: any
    statusRegexp: any
    commandTerminator: any
    commandDelay: any
    measureDelay: any
    newMeasureDelay: any
    measureCommand: any
    emptyAnswerValid: any


@contextmanager
def serial_connection(path, protocol, is_probing=False):
    probing_timeout = 1
    port_config = {
        "baudrate": protocol.baudrate,
        "bytesize": protocol.bytesize,
        "stopbits": protocol.stopbits,
        "parity": protocol.parity,
        "timeout": probing_timeout if is_probing else protocol.timeout,
        "writeTimeout": probing_timeout if is_probing else protocol.writeTimeout,
    }
    connection = serial.Serial(path, **port_config)
    try:
        yield connection
    finally:
        connection.close()


class CompatSerialDriver(Driver):
    _protocol = None
    connection_type = "serial"

    STATUS_CONNECTED = "connected"
    STATUS_ERROR = "error"
    STATUS_CONNECTING = "connecting"
    STATUS_DISCONNECTED = "disconnected"

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self._actions.update({
            "get_status": self._push_status,
        })
        self.device_connection = "serial"
        self._device_lock = Lock()
        self._status = {
            "status": self.STATUS_CONNECTING,
            "message_title": "",
            "message_body": "",
        }
        self._connection = None
        self._set_name()

    def _get_raw_response(connection):
        raise NotImplementedError()

    def _push_status(self):
        self.data["status"] = self._status

    def _set_name(self):
        try:
            name = ("%s serial %s" % (self._protocol.name, self.device_type)).title()
        except Exception:
            name = "Unknown Serial Device"
        self.device_name = name

    def _take_measure(self):
        raise NotImplementedError()

    def _do_action(self, data):
        with self._device_lock:
            try:
                self._actions[data["action"]](data)
                time.sleep(self._protocol.commandDelay)
                self._status = {
                    "status": self.STATUS_CONNECTED,
                    "message_title": "",
                    "message_body": "",
                }
            except Exception:
                msg = f'An error occurred while performing action "{data}" on "{self.device_name}"'
                _logger.exception(msg)
                self._status = {
                    "status": self.STATUS_ERROR,
                    "message_title": msg,
                    "message_body": traceback.format_exc(),
                }
            self._push_status()

    def action(self, data):
        self.data["owner"] = data.get("session_id")
        self.data["action_args"] = {**data}

        if self._connection and self._connection.isOpen():
            self._do_action(data)
        else:
            with serial_connection(self.device_identifier, self._protocol) as connection:
                self._connection = connection
                self._do_action(data)
        event_manager.device_changed(self, data)

    def run(self):
        try:
            with serial_connection(self.device_identifier, self._protocol) as connection:
                self._connection = connection
                self._status["status"] = self.STATUS_CONNECTED
                self._push_status()
                while not self._stopped.is_set():
                    self._take_measure()
                    time.sleep(self._protocol.newMeasureDelay)
                self._status["status"] = self.STATUS_DISCONNECTED
                self._push_status()
        except Exception:
            msg = "Error while reading %s" % self.device_name
            _logger.exception(msg)
            self._status = {
                "status": self.STATUS_ERROR,
                "message_title": msg,
                "message_body": traceback.format_exc(),
            }
            self._push_status()


SerialProtocol = CompatSerialProtocol
SerialDriver = CompatSerialDriver