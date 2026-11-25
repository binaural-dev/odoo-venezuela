from datetime import datetime, timedelta

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import json
import logging

_logger = logging.getLogger(__name__)

# Vigencia del token de /Autenticacion cuando la respuesta no trae
# ``expiracion`` (TFHKA emite tokens de 12 h).
TFHKA_TOKEN_LIFETIME = timedelta(hours=12)
# Margen con el que se renueva el token antes de su vencimiento, para no
# llegar a la imprenta con un token que expira en pleno envío.
TFHKA_TOKEN_REFRESH_MARGIN = timedelta(minutes=30)


class ResCompany(models.Model):
    _inherit = "res.company"
    
    username_tfhka = fields.Char()
    password_tfhka = fields.Char()
    url_tfhka = fields.Char()
    token_auth_tfhka = fields.Char()
    token_expiry_tfhka = fields.Datetime(
        string="TFHKA Token Expiry",
        copy=False,
        readonly=True,
        help="Expiration (UTC) of the current TFHKA token, as returned by "
        "/Autenticacion. The token is reused until shortly before this date "
        "and refreshed automatically afterwards.",
    )
    invoice_digital_tfhka = fields.Boolean()
    dispatch_guide_digital_tfhka = fields.Boolean()
    sequence_validation_tfhka = fields.Boolean(default=True)
    digitalization_with_payment_tfhka = fields.Boolean(default=False)
    payment_mode_tfhka = fields.Selection(
        [
            ("credit", "Credit Payment"),
            ("cash", "Cash Payment"),
        ],
        string="TFHKA Payment Mode",
        default="credit",
        help="Only applies when 'Digital invoicing with payment "
        "registration' is enabled. 'Credit Payment' keeps the current flow "
        "(the invoice can be digitalized with or without a registered "
        "payment). 'Cash Payment' blocks digitalization until the "
        "invoice's payment is in process, fully paid, or the invoice has "
        "been reversed.",
    )
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

    @api.onchange("digitalization_with_payment_tfhka")
    def _onchange_digitalization_with_payment_tfhka(self):
        for company in self:
            if not company.digitalization_with_payment_tfhka:
                company.payment_mode_tfhka = "credit"

    def write(self, vals):
        if "digitalization_with_payment_tfhka" in vals and not vals[
            "digitalization_with_payment_tfhka"
        ]:
            vals["payment_mode_tfhka"] = "credit"
        return super().write(vals)

    def generate_token_tfhka(self):
        self.ensure_one()
        self._validate_tfhka_credentials()

        payload = {
            "usuario": self.username_tfhka,
            "clave": self.password_tfhka
        }
        response = self.env["tfhka.api.client"].authenticate(self, payload)
        self._handle_tfhka_response(response, payload)

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
        # La respuesta trae el token Bearer: se enmascara antes de guardarla
        # para que no quede visible en el historial de llamadas (ticket 16683).
        response_text = (
            json.dumps(
                self.env["tfhka.api.log"]._sanitize_payload(response_data),
                default=str,
                indent=2,
            )
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
            self.write({
                "token_auth_tfhka": data["token"],
                "token_expiry_tfhka": self._parse_tfhka_token_expiry(data.get("expiracion")),
            })
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

    @api.model
    def _parse_tfhka_token_expiry(self, value):
        """Converts the ``expiracion`` returned by /Autenticacion (UTC ISO
        8601, e.g. ``2025-01-31T23:59:59.1234567Z``) into a naive UTC
        datetime. Falls back to now + 12 h when it's missing, malformed or
        already in the past -- the 401 retry in ``tfhka.api.client`` still
        covers a token the API invalidates earlier than announced."""
        now = fields.Datetime.now()
        fallback = now + TFHKA_TOKEN_LIFETIME
        if not isinstance(value, str) or len(value) < 19:
            return fallback
        try:
            expiry = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return fallback
        return expiry if expiry > now else fallback

    def _tfhka_token_needs_refresh(self):
        """True when the stored token is about to expire and must be renewed
        BEFORE calling TFHKA (ticket 16683), instead of waiting for the API
        to answer 401.

        A token without a known expiry (stored before this field existed)
        keeps the previous behavior: it's reused until TFHKA rejects it
        with 401. An empty token is not refreshed here either, so the
        existing "token is empty" configuration error is preserved."""
        self.ensure_one()
        if not self.token_auth_tfhka or not self.token_expiry_tfhka:
            return False
        return self.token_expiry_tfhka - TFHKA_TOKEN_REFRESH_MARGIN <= fields.Datetime.now()
