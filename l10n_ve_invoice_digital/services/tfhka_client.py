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

    def _request(self, company, endpoint_key, payload, _retried=False):
        """Ejecuta un POST a TFHKA y devuelve la respuesta decodificada.

        Preserva el protocolo actual: ``codigo == "200"`` ok, ``codigo == "203"``
        con validaciones en ``ultimo_documento`` -> 0, 401 -> regenera el token y
        reintenta **una sola vez**, HTTP != 200 -> ``UserError``, y
        ``RequestException`` -> ``UserError``.
        """
        base_url = self._base_url(company)
        endpoint = TFHKA_ENDPOINTS.get(endpoint_key)

        if not endpoint:
            raise UserError(_("Endpoint '%(endpoint_key)s' is not defined.", endpoint_key=endpoint_key))

        url = f"{base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token(company)}"}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TFHKA_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                if data.get("codigo") == "200":
                    return data
                elif data.get("codigo") == "203" and data.get("validaciones") and endpoint_key == "ultimo_documento":
                    return 0
                else:
                    _logger.error("Error in the API response: %s \n%s", data.get('mensaje'), data.get('validaciones'))
                    raise UserError(_("Error in the API response: %(message)s \n%(validation)s", message=data.get('mensaje'), validation=data.get('validaciones')))
            if response.status_code == 401:
                if _retried:
                    _logger.error("TFHKA authentication still failing after token refresh.")
                    raise UserError(_("TFHKA authentication failed: the token is invalid even after refreshing it. Please verify the credentials."))
                _logger.error("Error 401: Invalid or expired token. Refreshing and retrying once.")
                company.generate_token_tfhka()
                return self._request(company, endpoint_key, payload, _retried=True)
            else:
                _logger.error("HTTP error %s: %s", response.status_code, response.text)
                raise UserError(_("HTTP error %(status_code)s: %(text)s", status_code=response.status_code, text=response.text))
        except requests.exceptions.RequestException as e:
            _logger.error("Error connecting to the API: %s", e)
            raise UserError(_("Error connecting to the API: %(error)s", error=e))

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def emit(self, company, payload):
        """POST /Emision. Devuelve la respuesta validada."""
        return self._request(company, "emision", payload)

    def annul(self, company, payload):
        """POST /Anular. Anula un documento digital (serie/tipo/numero + motivo)."""
        return self._request(company, "anular", payload)

    def get_last_document_number(self, company, document_type, series=""):
        """POST /UltimoDocumento. Devuelve el último número (0 si no existe)."""
        payload = {
            "serie": series,
            "tipoDocumento": document_type,
        }
        response = self._request(company, "ultimo_documento", payload)

        if response == 0:
            return response
        else:
            document_number = response["numeroDocumento"] if response["numeroDocumento"] else response
            return document_number

    def query_numbering(self, company, series=""):
        """POST /ConsultaNumeraciones. Valida que la serie exista y tenga rango."""
        payload = {
            "serie": series,
            "tipoDocumento": "",
            "prefix": "",
        }
        response = self._request(company, "consulta_numeraciones", payload)

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
                raise UserError(_("The series '%(series)s' is not configured in The Factory HKA. Please contact the administrator.", series=series))

            if not approves:
                raise UserError(_("The numbering range is exhausted. Please contact the administrator."))

            return
