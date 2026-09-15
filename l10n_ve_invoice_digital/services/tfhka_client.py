import json
import logging
import threading

import requests

from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Endpoints de la imprenta digital de The Factory HKA (relativos a company.url_tfhka).
TFHKA_ENDPOINTS = {
    "emision": "/Emision",
    "ultimo_documento": "/UltimoDocumento",
    "consulta_numeraciones": "/ConsultaNumeraciones",
    "anular": "/Anular",
    "autenticacion": "/Autenticacion",
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

    def _log_call(
        self, company, endpoint_key, payload, origin, status_code, response_payload, success
    ):
        log_vals = {
            "company_id": company.id,
            "endpoint": TFHKA_ENDPOINTS.get(endpoint_key, endpoint_key),
            "http_method": "POST",
            "request_payload": json.dumps(
                self.env["tfhka.api.log"]._sanitize_payload(payload),
                default=str,
                indent=2,
            )
            if payload
            else False,
            "status_code": status_code,
            "response_payload": response_payload if response_payload is not None else False,
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
        if getattr(threading.current_thread(), "testing", False):
            # En tests, cada test corre en su propio savepoint que se
            # revierte al terminar; usar un cursor aparte haría que estos
            # registros persistieran de verdad en la base y se filtraran
            # entre tests (incluidos los de otros archivos que también
            # ejercitan la API TFHKA). ``registry.in_test_mode()`` no sirve
            # acá: ese flag depende de ``registry.enter_test_mode()``, que no
            # todos los runners de test invocan; ``current_thread().testing``
            # es el flag que Odoo activa siempre al correr tests (mismo
            # patrón que usa el core, ver account_move.py/res_partner.py) y
            # es lo que hay que chequear para saber si el cursor normal va a
            # ser revertido por un savepoint de test. Se crea entonces con el
            # cursor normal, como cualquier otro dato de test.
            self.env["tfhka.api.log"].sudo().create(log_vals)
            return
        # Se persiste en un cursor propio con commit inmediato: cuando la
        # llamada falla, el error se relanza como UserError y escala hasta el
        # usuario, y Odoo revierte toda la transacción en curso -- sin un
        # cursor independiente, el registro del intento fallido se perdería
        # junto con el resto del rollback. Fallos al loguear no deben romper
        # el flujo de facturación, por eso quedan contenidos.
        try:
            with self.env.registry.cursor() as log_cr:
                api.Environment(log_cr, SUPERUSER_ID, {})["tfhka.api.log"].create(log_vals)
        except Exception:
            _logger.exception("TFHKA: failed to persist API call log entry")

    def _request(self, company, endpoint_key, payload, _retried=False, origin=None):
        """Ejecuta un POST a TFHKA y devuelve la respuesta decodificada.

        Preserva el protocolo actual: ``codigo == "200"`` ok, ``codigo == "203"``
        con validaciones en ``ultimo_documento`` -> 0, 401 -> regenera el token y
        reintenta **una sola vez**, HTTP != 200 -> ``UserError``, y
        ``RequestException`` -> ``UserError``.

        Cada intento (incluido el reintento por 401) se registra en
        ``tfhka.api.log`` con el request saneado y la respuesta.
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
                    self._log_call(
                        company,
                        endpoint_key,
                        payload,
                        origin,
                        response.status_code,
                        json.dumps(data, default=str, indent=2),
                        True,
                    )
                    return data
                elif data.get("codigo") == "203" and data.get("validaciones") and endpoint_key == "ultimo_documento":
                    self._log_call(
                        company,
                        endpoint_key,
                        payload,
                        origin,
                        response.status_code,
                        json.dumps(data, default=str, indent=2),
                        True,
                    )
                    return 0
                else:
                    _logger.error("Error in the API response: %s \n%s", data.get('mensaje'), data.get('validaciones'))
                    self._log_call(
                        company,
                        endpoint_key,
                        payload,
                        origin,
                        response.status_code,
                        json.dumps(data, default=str, indent=2),
                        False,
                    )
                    raise UserError(_("Error in the API response: %(message)s \n%(validation)s", message=data.get('mensaje'), validation=data.get('validaciones')))
            if response.status_code == 401:
                if _retried:
                    _logger.error("TFHKA authentication still failing after token refresh.")
                    self._log_call(
                        company, endpoint_key, payload, origin, response.status_code, response.text, False
                    )
                    raise UserError(_("TFHKA authentication failed: the token is invalid even after refreshing it. Please verify the credentials."))
                _logger.error("Error 401: Invalid or expired token. Refreshing and retrying once.")
                self._log_call(
                    company, endpoint_key, payload, origin, response.status_code, response.text, False
                )
                company.generate_token_tfhka()
                return self._request(company, endpoint_key, payload, _retried=True, origin=origin)
            else:
                _logger.error("HTTP error %s: %s", response.status_code, response.text)
                self._log_call(
                    company, endpoint_key, payload, origin, response.status_code, response.text, False
                )
                raise UserError(_("HTTP error %(status_code)s: %(text)s", status_code=response.status_code, text=response.text))
        except requests.exceptions.RequestException as e:
            _logger.error("Error connecting to the API: %s", e)
            self._log_call(company, endpoint_key, payload, origin, None, str(e), False)
            raise UserError(_("Error connecting to the API: %(error)s", error=e))

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
        """POST /UltimoDocumento. Devuelve el último número (0 si no existe)."""
        payload = {
            "serie": series,
            "tipoDocumento": document_type,
        }
        response = self._request(company, "ultimo_documento", payload, origin=origin)

        if response == 0:
            return response
        else:
            document_number = response["numeroDocumento"] if response["numeroDocumento"] else response
            return document_number

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
                raise UserError(_("The series '%(series)s' is not configured in The Factory HKA. Please contact the administrator.", series=series))

            if not approves:
                raise UserError(_("The numbering range is exhausted. Please contact the administrator."))

            return
