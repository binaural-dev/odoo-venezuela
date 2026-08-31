import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class BcvSyncController(http.Controller):
    """Receiving side of the contract documented in ``ODOO_INTEGRATION.md``
    from the BCV Sync repo (external service that scrapes bcv.org.ve and
    POSTs to each configured Odoo instance). This controller is
    deliberately thin: authenticates, validates the payload shape, and
    delegates the rest (parsing each rate, idempotency, business-day
    decision) to ``res.company``/``res.currency.rate``.
    """

    @http.route(
        "/api/tasas-bcv",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def receive_bcv_rates(self, **kwargs):
        token = self._extract_bearer_token(
            request.httprequest.headers.get("Authorization")
        )
        if not token:
            return self._json_response(
                {"ok": False, "error": "missing_or_invalid_authorization_header"},
                401,
            )

        company = request.env["res.company"]._bcv_sync_get_company_by_token(token)
        if not company:
            _logger.warning(
                "BCV Sync: authentication attempt with an invalid token "
                "(or no company configured for that token)."
            )
            return self._json_response({"ok": False, "error": "invalid_token"}, 401)

        try:
            raw_body = request.httprequest.get_data(as_text=True) or "{}"
            payload = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError):
            return self._json_response(
                {"ok": False, "error": "request body is not valid JSON"}, 400
            )

        if not isinstance(payload, dict) or not isinstance(payload.get("tasas"), list):
            return self._json_response(
                {
                    "ok": False,
                    "error": "invalid payload: expected {'tasas': [...]}",
                },
                400,
            )
        if not all(isinstance(entry, dict) for entry in payload["tasas"]):
            return self._json_response(
                {"ok": False, "error": "invalid payload: 'tasas' must be a list of objects"},
                400,
            )

        try:
            summary = company._bcv_sync_process_tasas(payload["tasas"])
        except Exception:
            _logger.exception(
                "BCV Sync: unexpected error processing the payload for %s",
                company.display_name,
            )
            return self._json_response(
                {"ok": False, "error": "internal error processing the payload"}, 500
            )

        _logger.info(
            "BCV Sync: payload processed for %s -- applied=%s skipped=%s",
            company.display_name,
            summary["applied"],
            summary["skipped"],
        )
        return self._json_response(
            {"ok": True, "applied": summary["applied"], "skipped": summary["skipped"]},
            200,
        )

    @staticmethod
    def _extract_bearer_token(header_value):
        """Returns the token from an ``Authorization: Bearer <token>``
        header, or ``None`` if the header is missing or malformed."""
        if not header_value:
            return None
        parts = header_value.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        token = parts[1].strip()
        return token or None

    @staticmethod
    def _json_response(data, status):
        return request.make_json_response(data, status=status)
