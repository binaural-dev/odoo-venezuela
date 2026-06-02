import logging
import threading

import requests

from odoo import models, fields, api, _


_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    serial_machine = fields.Char(related="config_id.iface_fiscal_data_module.serial_machine")
    iot_mf = fields.Many2one(related="config_id.iface_fiscal_data_module")
    report_z = fields.Char()

    def set_report_z(self, values):
        self.write({"report_z": int(values["data"]["_dailyClosureCounter"]) + 1})

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("code_fiscal_printer")
        return res

    def _loader_params_pos_config(self):
        res = super()._loader_params_pos_config()
        res["search_params"]["fields"].extend(
            [
                "access_button_mf",
                "message_in_head",
                "mf_debug",
                "iot_ip",
            ]
        )
        return res

    def _loader_params_iot_device(self):
        res = super()._loader_params_iot_device()
        res["search_params"]["fields"].append("flag_21")
        res["search_params"]["fields"].append("traditional_line")
        res["search_params"]["fields"].append("iot_ip")
        return res

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("fiscal_code")
        return res

    @api.model
    def proxy_fiscal_action(self, action, payload):
        """Proxy fiscal print actions through the Odoo server asynchronously.

        The print request is dispatched in a background thread so the Odoo
        worker returns immediately, avoiding blocking the worker pool during
        slow serial communication with the fiscal printer.
        """
        payload = payload or {}

        config_id = payload.get("config_id")
        config = self.env["pos.config"].browse(config_id) if config_id else self.env["pos.config"]
        if not config.exists():
            return {
                "value": {
                    "valid": False,
                    "message": _("No se encontro la configuracion POS"),
                }
            }

        iot_ip = payload.get("iot_ip") or config.iot_ip
        if not iot_ip:
            return {
                "value": {
                    "valid": False,
                    "message": _("No se pudo determinar la IP del IoT Box"),
                }
            }

        iot_host = iot_ip if ":" in iot_ip else f"{iot_ip}:8069"

        device_id = config.iface_fiscal_data_module.identifier if config.iface_fiscal_data_module else "fiscal_data_module"

        _logger.info(
            "POS MF proxy_fiscal_action: config=%s device=%s action=%s iot=%s",
            config.id,
            device_id,
            action,
            iot_host,
        )

        def _do_action():
            try:
                response = requests.post(
                    f"http://{iot_host}/iot_drivers/action",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "call",
                        "params": {
                            "session_id": config.id,
                            "device_identifier": device_id,
                            "data": {
                                "action": action,
                                "data": payload,
                            },
                        },
                    },
                    timeout=300,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                _logger.info(
                    "POS MF proxy_fiscal_action: async OK action=%s",
                    action,
                )
            except Exception as exc:
                _logger.error(
                    "POS MF proxy_fiscal_action: async FAILED action=%s error=%s",
                    action,
                    exc,
                )

        thread = threading.Thread(target=_do_action, daemon=True)
        thread.start()

        _logger.info(
            "POS MF proxy_fiscal_action: dispatched async action=%s",
            action,
        )
        return {"value": {"valid": True, "message": "Impresion fiscal despachada"}}
