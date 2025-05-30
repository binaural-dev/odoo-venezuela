from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
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
    sequence_validation_tfhka = fields.Boolean(default=True)
    
    def generate_token_tfhka(self):
        self.ensure_one()
        self._validate_tfhka_credentials()

        url = self.url_tfhka.rstrip("/") + "/Autenticacion"
        payload = {
            "usuario": self.username_tfhka,
            "clave": self.password_tfhka
        }

        try:
            response = requests.post(url, json=payload)
            self._handle_tfhka_response(response)
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error connecting to the TFHKA API: {e}")
            raise ValidationError(_("Error connecting to the TFHKA API: %s") % e)

    def _validate_tfhka_credentials(self):
        if not self.username_tfhka:
            raise UserError(_("You must register the Username for TFHKA."))
        if not self.password_tfhka:
            raise UserError(_("You must register the Password for TFHKA."))
        if not self.url_tfhka:
            raise UserError(_("You must register the URL for TFHKA."))
        _logger.info("TFHKA credentials validated successfully.")

    def _handle_tfhka_response(self, response):
        data = response.json()
        if response.status_code == 200 and data.get("codigo") == 200:
            try:
                self._process_tfhka_response_data(data)
            except ValueError:
                _logger.error(f"Error decoding JSON: {response.text}")
                raise ValidationError(_("Error processing TFHKA API response."))
        else:
            self._handle_tfhka_http_error(response, data)

    def _process_tfhka_response_data(self, data):
        if "token" in data:
            self.token_auth_tfhka = data["token"]
            _logger.info(f"Token generated successfully: {self.token_auth_tfhka}.")
        else:
            _logger.error(f"The 'token' field is not found in the response: {data}")
            raise ValidationError(_("TFHKA API response does not contain 'token'."))

    def _handle_tfhka_http_error(self, response, data):
        message = data.get("mensaje")
        if message:
            raise ValidationError(_("Authentication error: %(message)s") % {'message': message})
        else:
            raise ValidationError(_("Error in the TFHKA API: %(status_code)s") % {'status_code': response.status_code})