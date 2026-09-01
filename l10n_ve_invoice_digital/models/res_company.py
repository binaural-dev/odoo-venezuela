from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import json
import requests
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"
    
    username_tfhka = fields.Char()
    password_tfhka = fields.Char()
    url_tfhka = fields.Char()
    token_auth_tfhka = fields.Char()
    invoice_digital_tfhka = fields.Boolean()
    dispatch_guide_digital_tfhka = fields.Boolean()
    sequence_validation_tfhka = fields.Boolean(default=True)
    digitalization_with_payment_tfhka = fields.Boolean(default=False)
    # Habilita el flag multi-moneda a nivel compañía.
    # Cuando está activo, aparece el checkbox "Multi-Currency Invoice" en cada
    # factura, y dentro de este un selector VES/USD para elegir la moneda de
    # las líneas de producto.
    multi_currency_invoice_tfhka = fields.Boolean(
        string="Multi-currency digital invoicing",
        default=False,
        help="When enabled, invoices can be digitalized with multi-currency support "
             "(VES or USD line prices + dual totals if USD selected). An additional "
             "checkbox + currency selector will appear on each invoice."
    )
    mix_invoicing_tfhka = fields.Boolean(default=True, string="Allow Mixed Invoicing")
    mix_invoicing_type_tfhka = fields.Selection(
        [
            ("free_form", "Free form"),
            ("fiscal_machine", "Fiscal Machine"),
        ],
        default="free_form",
    )

    
    def generate_token_tfhka(self):
        self.ensure_one()
        self._validate_tfhka_credentials()

        url = self.url_tfhka.rstrip("/") + "/Autenticacion"
        payload = {
            "usuario": self.username_tfhka,
            "clave": self.password_tfhka
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            self._handle_tfhka_response(response, payload)
        except requests.exceptions.RequestException as e:
            _logger.error("Error connecting to the TFHKA API: %s", e)
            self._log_tfhka_auth_call(payload, None, str(e), False)
            raise ValidationError(_("Error connecting to the TFHKA API: %s", e))

    def _validate_tfhka_credentials(self):
        if not self.username_tfhka:
            raise UserError(_("You must register the Username for TFHKA."))
        if not self.password_tfhka:
            raise UserError(_("You must register the Password for TFHKA."))
        if not self.url_tfhka:
            raise UserError(_("You must register the URL for TFHKA."))
        _logger.info("TFHKA credentials validated successfully.")

    def _log_tfhka_auth_call(self, payload, status_code, response_data, success):
        """Registra en tfhka.api.log el intento de autenticación (Autenticacion).

        A diferencia del resto de los endpoints, la autenticación no pasa por
        ``tfhka.api.client._request`` (usa usuario/clave en vez del token
        Bearer), así que se registra explícitamente aquí para que también
        quede en el historial de llamadas a la API.
        """
        response_text = (
            json.dumps(response_data, default=str, indent=2)
            if isinstance(response_data, dict)
            else (str(response_data) if response_data is not None else False)
        )
        self.env["tfhka.api.client"]._log_call(
            self, "autenticacion", payload, None, status_code, response_text, success
        )

    def _handle_tfhka_response(self, response, payload=None):
        data = response.json()
        if response.status_code == 200 and data.get("codigo") == 200:
            try:
                self._process_tfhka_response_data(data)
            except ValueError:
                _logger.error(f"Error decoding JSON: {response.text}")
                self._log_tfhka_auth_call(payload, response.status_code, data, False)
                raise ValidationError(_("Error processing TFHKA API response."))
            except ValidationError:
                self._log_tfhka_auth_call(payload, response.status_code, data, False)
                raise
            else:
                self._log_tfhka_auth_call(payload, response.status_code, data, True)
        else:
            self._log_tfhka_auth_call(payload, response.status_code, data, False)
            self._handle_tfhka_http_error(response, data)

    def _process_tfhka_response_data(self, data):
        if "token" in data:
            self.token_auth_tfhka = data["token"]
            _logger.info("TFHKA token generated successfully.")
        else:
            _logger.error("The 'token' field is not found in the response: %s", data)
            raise ValidationError(_("TFHKA API response does not contain 'token'."))

    def _handle_tfhka_http_error(self, response, data):
        message = data.get("mensaje")
        if message:
            raise ValidationError(_("Authentication error: %(message)s", message=message))
        else:
            raise ValidationError(_("Error in the TFHKA API: %(status_code)s", status_code=response.status_code))