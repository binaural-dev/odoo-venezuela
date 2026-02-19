from odoo.http import request
import json
from odoo import http
import logging

_logger = logging.getLogger(__name__)


class StatusAccessController(http.Controller):

    @http.route(
        "/cadipa_hikvision/get_waiting_config", type="json", auth="user", methods=["POST"]
    )
    def get_waiting_config(self):
        """Endpoint para obtener la configuración de espera de la compañía actual.
        
        Returns:
            dict: Diccionario con cadipa_waiting_message y cadipa_waiting_color
        """
        try:
            company = request.env.company
            return {
                "waiting_message": company.cadipa_waiting_message or "Esperando...",
                "waiting_color": company.cadipa_waiting_color or "#2c3e50",
            }
        except Exception as e:
            _logger.error("Error obteniendo configuración de espera: %s", e)
            return {
                "waiting_message": "Esperando...",
                "waiting_color": "#2c3e50",
            }
    @http.route(
        "/cadipa_hikvision/test_message", type="json", auth="public", methods=["POST"]
    )
    def test_message(self, message=None):
        """Endpoint de prueba: recibe un mensaje y lo envía al bus.
        Acepta JSON-RPC (params.message) o JSON plano {"message": "..."}.
        """
        try:
            if message is None:
                body = request.httprequest.get_data(as_text=True)
                _logger.info("Body: %s", body)
                data = json.loads(body)
                message = data.get("message")

            channel = "cadipa_hikvision_test_channel"
            bus_message = {
                "data": {
                    "message": message,
                    "timestamp": request.env.cr.now().isoformat(),
                },
                "channel": channel,
                "type": "test_message",
            }

            request.env["bus.bus"]._sendone(channel, "notification", bus_message)

            return {"status": "success", "message": "Mensaje enviado al bus"}
        except Exception as e:
            _logger.error("Error enviando mensaje de prueba: %s", e)
            return {"status": "error", "message": str(e)}