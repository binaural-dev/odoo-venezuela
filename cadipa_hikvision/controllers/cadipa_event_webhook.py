import logging
from datetime import datetime, timezone

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.binaural_hikvision.controllers.hikcentral_event_webhook import (
        HikcentralWebhookController,
    )
except ImportError:
    _logger.error("CADIPA: binaural_hikvision module not found.")


class CadipaHikcentralWebhookController(HikcentralWebhookController):

    def _process_events(self, events_list):
        super()._process_events(events_list)

        hik_users_model = request.env["hikcentral.users"].sudo()
        company_model = request.env["res.company"].sudo()

        company_creds = company_model.search(
            [
                ("hikcentral_base_url", "!=", False),
                ("hikcentral_user_key", "!=", False),
                ("hikcentral_user_secret", "!=", False),
            ],
            limit=1,
        )

        if not company_creds:
            return

        for event_data in events_list:
            event_api_id = (event_data or {}).get("eventId")
            if not event_api_id:
                continue
            event_type = str(event_data.get("eventType", ""))
            event_details = (event_data or {}).get("data", {}) or {}
            person_api_id = event_details.get("personCode")

            hik_user = hik_users_model.search(
                [("hikcentral_person_code", "=", person_api_id)], limit=1
            )

            _logger.info("CADIPA: Hik user: %s", hik_user)

            if event_type == "198914" and person_api_id and person_api_id != "-1":
                self._revoke_access_if_visitor_with_qr(
                    hik_user, person_api_id, company_creds
                )

            if hik_user:
                device_index = event_data.get("srcIndex")
                if not device_index:
                    continue

                device_model = request.env["hikcentral.device"].sudo()
                device = device_model.search(
                    [("index_code", "=", device_index)], limit=1
                )

                if not device:
                    _logger.info(
                        "CADIPA: Device not found: %s (index_code: %s)",
                        device_index,
                        device_index,
                    )
                    continue

                if not self._is_device_configured(device):
                    _logger.info(
                        "CADIPA: Device %s (index_code: %s) is not configured in any rule. "
                        "Omitting processing.",
                        device.name,
                        device_index,
                    )
                    continue

                not_solvent, revoke_access, membership = self._check_solvency_status(
                    hik_user, company_creds
                )
                
                if revoke_access and membership:
                    root_user = request.env.ref("base.user_root")
                    membership.with_user(root_user).write(
                        {"suspended_membership": True}
                    )
                    _logger.info(
                        "CADIPA: Membership suspended (suspended_membership=True): %s",
                        membership.display_name,
                    )

                message_config = self._get_message_config(
                    hik_user,
                    device,
                    not_solvent=not_solvent,
                    revoke_access=revoke_access,
                )

                _logger.info("CADIPA: Message config to send to bus: %s", message_config)

                if message_config:
                    self._create_access_history(
                        event_data, hik_user, device, membership, message_config
                    )
                    self._send_hikuser_name_to_bus(
                        person_api_id, event_type, message_config
                    )
                else:
                    _logger.info(
                        "CADIPA: No configuration found for device %s (index_code: %s)",
                        device.name,
                        device_index,
                    )

    def _parse_event_occurred_at(self, event_data):
        """Parse happenTime from event_data; return naive UTC datetime or None."""
        if not event_data:
            return None
        happen_time_str = event_data.get("happenTime")
        if not happen_time_str:
            return None
        try:
            aware_dt = datetime.strptime(
                happen_time_str, "%Y-%m-%dT%H:%M:%S%z"
            )
            return aware_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

    def _create_access_history(
        self, event_data, hik_user, device, membership, message_config
    ):
        """Create a cadipa.access.history record for this member/affiliate access attempt."""
        if not hik_user or not hik_user.partner_id or not message_config:
            return
        code = message_config.code
        result_map = {
            "1": "allowed",
            "2": "pending_payment",
            "3": "denied",
        }
        result = result_map.get(code)
        if not result:
            return
        occurred_at = self._parse_event_occurred_at(event_data)
        if not occurred_at:
            occurred_at = fields.Datetime.now()
        membership_id = membership.id if membership else False
        membership_number = membership.number if membership else ""
        is_beneficiary = False
        if membership and hik_user.partner_id:
            is_beneficiary = (
                hik_user.partner_id in membership.beneficiary_partner_ids
            )
        reason = message_config.message or message_config.name or ""
        request.env["cadipa.access.history"].sudo().create(
            {
                "occurred_at": occurred_at,
                "partner_id": hik_user.partner_id.id,
                "membership_id": membership_id,
                "membership_number": membership_number,
                "device_id": device.id if device else False,
                "result": result,
                "access_status_code": code,
                "reason": reason,
                "is_beneficiary": is_beneficiary,
            }
        )
        _logger.info("CADIPA: Access history created: %s", access_history)

    def _is_device_configured(self, device):
        """Checks if the device is configured in at least one message rule.

        Args:
            device: hikcentral.device record

        Returns:
            bool: True if the device is present in at least one configuration, False otherwise
        """
        if not device:
            return False

        try:
            config_model = request.env["realtime.message.config"].sudo()
            configs = config_model.search([])
            for config in configs:
                if device in config.device_ids:
                    return True
            return False
        except Exception as e:
            _logger.warning(
                "CADIPA: Error verificando si dispositivo está configurado: %s", e
            )
            return False

    def _get_message_config(
        self, hik_user, device, not_solvent=False, revoke_access=False
    ):
        """Determines which message configuration to show based on the conditions.

        First determines which configuration code to apply (1, 2 or 3) based on the user's status.
        revoke_access has priority (code 3), then not_solvent (code 2), then end_date (3 or 1).
        Only returns configuration if the device matches the corresponding rule.

        Args:
            hik_user: Record of hikcentral.users
            device: Record of hikcentral.device (required)
            not_solvent: Whether the user has pending not-yet-due membership invoices
            revoke_access: Whether access was revoked due to overdue attempt limit

        Returns:
            recordset: Record of realtime.message.config or None
        """
        if not device:
            return None

        try:
            config_model = request.env["realtime.message.config"].sudo()
            now = datetime.now()

            config_code = None

            if revoke_access:
                config_code = "3"
            elif not_solvent:
                config_code = "2"
            elif hik_user.end_date and hik_user.end_date < now:
                config_code = "3"
            else:
                config_code = "1"

            config = config_model.search([("code", "=", config_code)], limit=1)

            if not config:
                return None

            if device in config.device_ids:
                return config
            else:
                _logger.info(
                    "CADIPA: Device %s (index_code: %s) is not configured in the rule %s (code: %s). "
                    "Omitting message sending.",
                    device.name,
                    device.index_code,
                    config.name,
                    config_code,
                )
                return None

        except Exception as e:
            _logger.warning("CADIPA: Error getting message configuration: %s", e)
            return None

    def _send_hikuser_name_to_bus(
        self, person_code, event_type, message_config=None
    ):
        """Sends the hikuser name to the notification bus with message configuration.

        Args:
            person_code (str): Person code
            event_type (str): Event type
            message_config: Record of realtime.message.config (optional)
        """

        try:
            channel = "cadipa_hikvision_test_channel"

            _logger.info("CADIPA: Sending message configuration to bus: %s", message_config)
            bus_data = {
                "person_code": person_code,
                "event_type": event_type,
                "timestamp": request.env.cr.now().isoformat(),
            }

            if message_config:
                bus_data.update(
                    {
                        "message_config_code": message_config.code,
                        "message": message_config.message,
                        "color": message_config.color,
                        "duration_ms": message_config.duration_ms,
                    }
                )

            bus_message = {
                "data": bus_data,
                "channel": channel,
                "type": "hikuser_event",
            }

            request.env["bus.bus"]._sendone(channel, "notification", bus_message)
            _logger.info("CADIPA: Message sent to bus: %s", bus_message)
        except Exception as e:
            _logger.warning("CADIPA: Error sending name to bus: %s", e)

    def _check_solvency_status(self, hik_user, company_creds=None):
        """Check if the user (or their membership owner) has pending not-yet-due invoices
        and if access should be revoked due to overdue attempt limit.

        Returns:
            tuple: (not_solvent, revoke_access, membership)
        """
        if not hik_user or not hik_user.partner_id:
            return (False, False, None)

        action_partner_model = request.env["action.partner"].sudo()
        account_move_model = request.env["account.move"].sudo()
        today = fields.Date.today()

        membership = action_partner_model.search(
            [
                "|",
                ("owner_id", "=", hik_user.partner_id.id),
                ("beneficiary_partner_ids", "in", [hik_user.partner_id.id]),
                ("state", "=", "active"),
            ],
            limit=1,
        )

        if not membership or not membership.membership_type_plan.product_id:
            return (False, False, None)

        membership_product = membership.membership_type_plan.product_id
        owner_partner = membership.owner_id
        owner_hik_user = (
            request.env["hikcentral.users"]
            .sudo()
            .search([("partner_id", "=", owner_partner.id)], limit=1)
        )

        pending_invoices = account_move_model.search(
            [
                ("partner_id", "=", owner_partner.id),
                ("state", "=", "posted"),
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("invoice_line_ids.product_id", "=", membership_product.id),
                ("invoice_date_due", "<", today),
            ]
        )

        not_solvent = bool(pending_invoices)
        revoke_access = False

        if not_solvent and owner_hik_user:
            owner_hik_user.overdue_access_attempts = (
                owner_hik_user.overdue_access_attempts + 1
            )
            limit = (
                company_creds.cadipa_overdue_limit
                if company_creds
                else request.env.company.cadipa_overdue_limit
            )
            if owner_hik_user.overdue_access_attempts > limit:
                revoke_access = True

        return (not_solvent, revoke_access, membership)

    def _revoke_access_if_visitor_with_qr(
        self, hik_user, person_api_id, company_creds=None
    ):
        """Revoca el acceso de un hikuser si es visitante y cumple con las condiciones.

        Args:
            hik_user: Registro de hikcentral.users o recordset vacío
            person_api_id (str): Código de la persona
            company_creds: Registro de res.company con credenciales (opcional)

        Returns:
            bool: True si se revocó el acceso, False en caso contrario
        """
        if not hik_user:
            return False

        if not hik_user.is_visitor:
            return False

        try:
            _logger.info("CADIPA: Revoking access for visitor %s", person_api_id)
            if company_creds:
                hik_user.with_company(company_creds).action_revoke_access()
            else:
                hik_user.action_revoke_access()
            _logger.info(
                "CADIPA: Access revoked successfully for visitor %s", person_api_id
            )
            return True
        except Exception as e:
            _logger.error(
                f"CADIPA: Automatic revocation failed for {person_api_id}: {e}"
            )
            return False
