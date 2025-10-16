import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.binaural_hikvision.controllers.hikcentral_event_webhook import (
        HikcentralWebhookController,
    )
except ImportError:
    _logger.warning("CADIPA: No se encontró el módulo binaural_hikvision.")


class CadipaHikcentralWebhookController(HikcentralWebhookController):

    def _process_events(self, events_list):
        super()._process_events(events_list)
        _logger.info("CADIPA: Procesando eventos de webhook...")

        partner_model = request.env["res.partner"].sudo()
        bus = request.env["bus.bus"].sudo()
        channel_name = "hikvision_access_channel"
        channel = (
            request.env.cr.dbname,
            channel_name,
        )

        for event_data in events_list:
            event_details = (event_data or {}).get("data", {}) or {}
            person_api_id = event_details.get("personCode")

            partner = False
            if person_api_id and person_api_id != "-1":
                partner = partner_model.search([("vat", "=", person_api_id)], limit=1)

            if partner:
                if getattr(partner, "is_solvent", False):
                    status_text = "Acceso Permitido - Solvente"
                    bg_class = "bg-success"
                else:
                    status_text = "Acceso Permitido - NO SOLVENTE"
                    bg_class = "bg-warning"

                payload = {
                    "name": partner.name,
                    "status_text": status_text,
                    "bg_class": bg_class,
                    "image_url": f"/web/image/res.partner/{partner.id}/image_1920",
                }
            else:
                payload = {
                    "name": f"Usuario Desconocido ({person_api_id})",
                    "status_text": "No encontrado en el sistema",
                    "bg_class": "bg-danger",
                    "image_url": False,
                }

            try:
                # 1) Empaqueta el mensaje con type + payload
                message = {
                    "type": "access_control_event",
                    "payload": payload,
                }
                # 2) Envía con canal en formato (dbname, canal) y SOLO el message
                bus._sendone(channel, message)

                _logger.info("CADIPA: Notificación enviada: %s", payload.get("name"))
            except Exception as e:
                _logger.exception("CADIPA: Error enviando al bus: %s", e)
