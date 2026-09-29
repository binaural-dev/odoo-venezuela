import json
import logging

import requests

from odoo import _, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Endpoints de la imprenta digital de The Factory HKA (relativos a company.url_tfhka).
TFHKA_ENDPOINTS = {
    "emision": "/Emision",
    "ultimo_documento": "/UltimoDocumento",
    "consulta_numeraciones": "/ConsultaNumeraciones",
    "anular": "/Anular",
}

# Timeout (segundos) para las llamadas HTTP a TFHKA.
TFHKA_TIMEOUT = 10

# Marcador del mensaje de negocio de TFHKA para "no repitas esta consulta
# tan seguido" (ej. ConsultaNumeraciones llamado dos veces en <30s). Usado
# por tfhka.digitalization.mixin para decidir si vale la pena un único
# reintento con espera, en vez de tratarlo como cualquier otro error.
RATE_LIMIT_MESSAGE_MARKER = "realizada previamente"


def _is_rate_limit_message(message):
    return bool(message) and RATE_LIMIT_MESSAGE_MARKER in message.lower()


class TfhkaBusinessError(UserError):
    """UserError levantado cuando TFHKA respondió HTTP 200 con un ``codigo``
    de negocio distinto de éxito (200) o del caso especial 203+ultimo_documento.

    Lleva el código original en ``tfhka_code`` para que
    ``tfhka.digitalization.mixin`` pueda clasificar el fallo (error grave vs
    error de datos) sin tener que parsear el mensaje de negocio.
    """

    def __init__(self, message, tfhka_code=None):
        super().__init__(message)
        self.tfhka_code = tfhka_code


class TfhkaApiClient(models.AbstractModel):
    """Cliente HTTP de la API de The Factory HKA.

    Capa de transporte pura (paralela a ``unidigital.api.client``):
    autenticación, ejecución de la petición y normalización de la respuesta.
    La compañía se pasa **explícitamente** en cada método; este servicio nunca
    lee ``self.env.company``. El armado de los payloads vive en
    ``tfhka.document.service`` / ``tfhka.retention.service``.
    """

    _name = "tfhka.api.client"
    _description = "TFHKA API Client"

    def _base_url(self, company):
        if company.url_tfhka:
            return company.url_tfhka.rstrip("/")
        raise UserError(_("The URL is not configured in the company settings."))

    def _token(self, company):
        if company.token_auth_tfhka:
            return company.token_auth_tfhka
        raise ValidationError(_("Configuration error: The authentication token is empty."))

    def _log_call(self, company, endpoint, payload, origin, status_code, response_payload, success):
        log_vals = {
            "company_id": company.id,
            "endpoint": endpoint,
            "http_method": "POST",
            "request_payload": json.dumps(
                self.env["tfhka.api.log"]._sanitize_payload(payload),
                default=str,
                indent=2,
            )
            if payload
            else False,
            "status_code": status_code,
            "response_payload": str(response_payload) if response_payload is not None else False,
            "success": bool(success),
        }
        if origin:
            log_vals.update(
                {
                    "res_model": origin._name,
                    "res_id": origin.id,
                    "res_name": origin.display_name,
                }
            )

        # Persist in an isolated cursor: the caller often raises right after
        # this (e.g. a UserError for a business error TFHKA returned), which
        # rolls back the current transaction and would silently wipe out the
        # very log row we just wrote if it shared that transaction.
        try:
            with self.pool.cursor() as log_cr:
                self.env(cr=log_cr)["tfhka.api.log"].sudo().create(log_vals)
        except Exception:
            _logger.exception("TFHKA: failed to persist API log entry for %s", endpoint)

    def _request(self, company, endpoint_key, payload, _retried=False, origin=None):
        """Ejecuta un POST a TFHKA y devuelve la respuesta decodificada.

        Preserva el protocolo actual: ``codigo == "200"`` ok, ``codigo == "203"``
        con validaciones en ``ultimo_documento`` -> 0, 401 -> regenera el token y
        reintenta **una sola vez**, HTTP != 200 -> ``TfhkaBusinessError`` (con el
        ``codigo`` de negocio si el cuerpo lo trae -- TFHKA a veces devuelve el
        mismo shape ``{"codigo", "mensaje", "validaciones"}`` bajo un status HTTP
        distinto de 200, p. ej. 400 por un campo que excede su longitud), y
        ``RequestException`` -> ``UserError`` (sin código, es un fallo de
        transporte). Cada intento (incluido el reintento tras un 401) se
        registra en ``tfhka.api.log``.
        """
        base_url = self._base_url(company)
        endpoint = TFHKA_ENDPOINTS.get(endpoint_key)

        if not endpoint:
            raise UserError(
                _("Endpoint '%(endpoint_key)s' is not defined.") % {"endpoint_key": endpoint_key}
            )

        url = f"{base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token(company)}"}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TFHKA_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                # TFHKA devuelve "codigo" indistintamente como entero o cadena
                # según el endpoint; se normaliza para no depender del tipo.
                code = str(data.get("codigo"))
                response_json = json.dumps(
                    self.env["tfhka.api.log"]._sanitize_payload(data),
                    default=str,
                    indent=2,
                )
                if code == "200":
                    self._log_call(
                        company, endpoint, payload, origin, response.status_code, response_json, True
                    )
                    return data
                elif code == "203" and data.get("validaciones") and endpoint_key == "ultimo_documento":
                    self._log_call(
                        company, endpoint, payload, origin, response.status_code, response_json, False
                    )
                    return 0
                else:
                    _logger.error("Error in the API response: %s \n%s", data.get('mensaje'), data.get('validaciones'))
                    self._log_call(
                        company, endpoint, payload, origin, response.status_code, response_json, False
                    )
                    raise TfhkaBusinessError(
                        _("Error in the API response: %(message)s \n%(validation)s")
                        % {"message": data.get('mensaje'), "validation": data.get('validaciones')},
                        tfhka_code=code,
                    )
            if response.status_code == 401:
                if _retried:
                    _logger.error("TFHKA authentication still failing after token refresh.")
                    self._log_call(
                        company, endpoint, payload, origin, response.status_code, response.text, False
                    )
                    raise UserError(_("TFHKA authentication failed: the token is invalid even after refreshing it. Please verify the credentials."))
                _logger.error("Error 401: Invalid or expired token. Refreshing and retrying once.")
                self._log_call(
                    company, endpoint, payload, origin, response.status_code, response.text, False
                )
                company.generate_token_tfhka()
                return self._request(company, endpoint_key, payload, _retried=True, origin=origin)
            else:
                _logger.error("HTTP error %s: %s", response.status_code, response.text)
                self._log_call(
                    company, endpoint, payload, origin, response.status_code, response.text, False
                )
                # TFHKA doesn't always wrap a business error in HTTP 200 --
                # some validation failures (e.g. a field exceeding its max
                # length) come back as a non-200 HTTP status whose body is
                # still the same {"codigo", "mensaje", "validaciones"} shape.
                # Without this, those responses would raise a plain UserError
                # with no .tfhka_code, so the mixin could never classify them
                # as 'data_error' even for codes 203/205.
                tfhka_code = None
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = None
                if isinstance(error_data, dict) and "codigo" in error_data:
                    tfhka_code = str(error_data.get("codigo"))
                raise TfhkaBusinessError(
                    _("HTTP error %(status_code)s: %(text)s")
                    % {"status_code": response.status_code, "text": response.text},
                    tfhka_code=tfhka_code,
                )
        except requests.exceptions.RequestException as e:
            _logger.error("Error connecting to the API: %s", e)
            self._log_call(company, endpoint, payload, origin, None, str(e), False)
            raise UserError(_("Error connecting to the API: %(error)s") % {"error": e})

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def emit(self, company, payload, origin=None):
        """POST /Emision. Devuelve la respuesta validada."""
        return self._request(company, "emision", payload, origin=origin)

    def annul(self, company, payload, origin=None):
        """POST /Anular. Anula un documento digital (serie/tipo/numero + motivo)."""
        return self._request(company, "anular", payload, origin=origin)

    def get_last_document_number(self, company, document_type, series="", origin=None):
        """POST /UltimoDocumento. Devuelve el último número como entero (0 si no existe).

        ``numeroDocumento = 0`` es un valor legítimo: significa que la serie aún
        no tiene documentos emitidos, que es justo el caso de una instalación
        nueva. La comprobación por veracidad devolvía la respuesta completa (un
        dict) en ese caso, y los llamadores reventaban al hacer ``int(last) + 1``
        o ``last + 1``.
        """
        payload = {
            "serie": series,
            "tipoDocumento": document_type,
        }
        response = self._request(company, "ultimo_documento", payload, origin=origin)

        if not isinstance(response, dict):
            return int(response or 0)
        try:
            return int(response.get("numeroDocumento") or 0)
        except (TypeError, ValueError):
            _logger.warning(
                "TFHKA devolvio un numeroDocumento no numerico: %r",
                response.get("numeroDocumento"),
            )
            return 0

    def query_numbering(self, company, series="", origin=None):
        """POST /ConsultaNumeraciones. Valida que la serie exista y tenga rango."""
        payload = {
            "serie": series,
            "tipoDocumento": "",
            "prefix": "",
        }
        response = self._request(company, "consulta_numeraciones", payload, origin=origin)

        if response:
            approves = False
            found_series = False
            for numbering in response.get("numeraciones", []):
                series_tfhka = numbering.get("serie", "")
                if series_tfhka != series and series_tfhka != "NO APLICA":
                    continue

                end_number = numbering.get("hasta")
                start_number = numbering.get("correlativo")
                found_series = True

                if int(start_number) < int(end_number):
                    approves = True
                    break

            if not found_series:
                raise UserError(
                    _(
                        "The series '%(series)s' is not configured in The Factory HKA. "
                        "Please contact the administrator."
                    )
                    % {"series": series}
                )

            if not approves:
                raise UserError(_("The numbering range is exhausted. Please contact the administrator."))

            return
