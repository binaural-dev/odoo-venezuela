import logging
import json
import requests

from odoo import http, fields, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import date_utils
from datetime import datetime
import functools

_logger = logging.getLogger(__name__)


class ApiIoT(http.Controller):
    @http.route(
        "/iot_fiscal/ports", type="http", auth="public", methods=["GET"], csrf=False
    )
    def getFiscalPorts(self, **kw):
        iot_ids = request.env["iot.box"].sudo().search([("has_fiscal_machine", "=", True)])
        response = {}
        for iot in iot_ids:
            response[iot.identifier] = iot.fiscal_port_ids.mapped(lambda x: x.name)
        return json.dumps(response)


    @http.route(
        "/iot_blacklist/ports", type="http", auth="public", methods=["GET"], csrf=False
    )
    def getFiscalPortsToBlock(self, **kw):
        iot_ids = request.env["iot.box"].sudo().search([("blacklist", "=", True)])
        _logger.warning("IOT IDS TO BLOCK %s", iot_ids)
        response = {}
        for iot in iot_ids:
            response[iot.identifier] = iot.blacklist_port_ids.mapped(lambda x: x.name)
        return json.dumps(response)

    @http.route(
        "/l10n_ve_iot_mf/action", type="http", methods=["POST"], auth="user", csrf=False
    )
    def proxy_iot_action(self, **kwargs):
        """
        Proxy para enviar acciones al IoT Box desde el servidor Odoo.
        El navegador llama a este endpoint cuando no puede conectar
        directamente al IoT Box (mixed content o diferencias de red).
        """
        try:
            data = json.loads(request.httprequest.data)
            iot_ip = data.get("iot_ip")
            route = data.get("route")
            params = data.get("params")
            timeout = data.get("timeout", 120)

            _logger.info(
                "IoT proxy request: iot_ip=%s route=%s action=%s",
                iot_ip,
                route,
                (params or {}).get("action"),
            )

            # Most IoT boxes expose the hw_proxy server on port 8069.
            # Allow passing an explicit port as part of iot_ip (e.g. "10.0.0.2:8069").
            iot_host = iot_ip
            if iot_host and ":" not in iot_host:
                iot_host = f"{iot_host}:8069"

            _logger.info(
                "Proxying IoT action: http://%s/%s", iot_ip, route
            )
            
            response = requests.post(
                f"http://{iot_host}/{route}",
                json={"params": params},
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            _logger.info(
                "IoT proxy response: iot_ip=%s route=%s status=%s",
                iot_host,
                route,
                "ok",
            )
            _logger.info("IoT proxy response: %s", result)
            return json.dumps(result)
        except requests.exceptions.Timeout:
            _logger.error("IoT proxy timeout: %s/%s", iot_ip, route)
            return json.dumps({"error": "Timeout", "status": "timeout"})
        except requests.exceptions.ConnectionError as e:
            _logger.error("IoT proxy connection error: %s - %s", iot_ip, e)
            return json.dumps({"error": str(e), "status": "unreachable"})
        except Exception as e:
            _logger.error("IoT proxy error: %s", e)
            return json.dumps({"error": str(e), "status": "error"})
