import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.binaural_hikvision.controllers.hikcentral_event_webhook import (
        HikcentralWebhookController,
    )
except ImportError:
    _logger.error("CADIPA: No se encontró el módulo binaural_hikvision.")


class CadipaHikcentralWebhookController(HikcentralWebhookController):

    def _process_events(self, events_list):
        super()._process_events(events_list)

        hik_users_model = request.env["hikcentral.users"].sudo()
        company_model = request.env["res.company"].sudo()

        company_creds = company_model.search(
            [("hikcentral_base_url", "!=", False)], limit=1
        )

        if not company_creds:
            company_creds = request.env.ref(
                "base.main_company", raise_if_not_found=False
            )

        for event_data in events_list:
            event_type = str(event_data.get("eventType", ""))
            event_details = (event_data or {}).get("data", {}) or {}
            person_api_id = event_details.get("personCode")

            if event_type == "198914" and person_api_id and person_api_id != "-1":
                _logger.info(
                    "CADIPA: Procesando revocación automática para %s", person_api_id
                )

                hik_user = hik_users_model.search(
                    [("hikcentral_person_code", "=", person_api_id)], limit=1
                )

                if not hik_user:
                    return

                if not hik_user.is_visitor:
                    return

                _logger.info(
                    "CADIPA: Usuario encontrado: %s. Usando credenciales de: %s",
                    hik_user.name,
                    company_creds.name,
                )
                try:
                    if company_creds:
                        hik_user.with_company(
                            company_creds
                        ).action_revoke_access()
                    else:
                        hik_user.action_revoke_access()

                except Exception as e:
                    _logger.error(
                        f"CADIPA: Falló la revocación automática para {person_api_id}: {e}"
                    )
