import logging

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
        # Ensure our config flags are available in the POS frontend.
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

    def proxy_fiscal_action(self, action, payload):
        """Proxy fiscal print actions through the Odoo server.

        This is called from POS frontend with ``this.orm.call`` so each print
        request goes server -> IoT Box, avoiding browser network restrictions.
        """
        self.ensure_one()
        payload = payload or {}
        _logger.warning('payload %s', payload)

        iot_ip = payload.get("iot_ip") or self.config_id.iot_ip
        if not iot_ip:
            return {
                "value": {
                    "valid": False,
                    "message": _("No se pudo determinar la IP del IoT Box"),
                }
            }

        iot_host = iot_ip if ":" in iot_ip else f"{iot_ip}:8069"

        # Buscar el identifier del dispositivo fiscal
        device_id = self.config_id.iface_fiscal_data_module.identifier if self.config_id.iface_fiscal_data_module else False
        if not device_id:
            device_id = "fiscal_data_module"

        _logger.info(
            "POS MF proxy_fiscal_action: session=%s device=%s action=%s iot=%s",
            self.id,
            device_id,
            action,
            iot_host,
        )

        try:
            response = requests.post(
                f"http://{iot_host}/iot_drivers/action",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "call",
                    "params": {
                        "session_id": self.id,
                        "device_identifier": device_id,
                        "data": {
                            "action": action.replace("print_", ""),
                            "data": payload,
                        },
                    },
                },
                timeout=120,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            if isinstance(result, dict) and result.get("result"):
                _logger.info(
                    "POS MF proxy_fiscal_action: success action=%s",
                    action,
                )
                return {"value": {"valid": True, "message": "Accion enviada a la MF"}}

            return {"value": {"valid": False, "message": "Error al enviar a la MF"}}

        except Exception as exc:
            _logger.warning(
                "POS EEEEEEEEEEEEEEEEEEEEEEEEEEEEERRRRRRor MF proxy_fiscal_action: action=%s failed: %s",
                action,
                exc,
            )
            return {"value": {"valid": False, "message": str(exc)}}
