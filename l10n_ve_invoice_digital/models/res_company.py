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
    notify_email_tfhka = fields.Boolean(
        default=True,
        string="Email sending from The Factory HKA",
        help="When enabled, The Factory HKA will send the digitalized "
        "document to the customer by email. When disabled, the email will "
        "be sent directly from Odoo.",
    )
    mix_invoicing_tfhka = fields.Boolean(default=True, string="Allow Mixed Invoicing")
    mix_invoicing_type_tfhka = fields.Selection(
        [
            ("free_form", "Free form"),
            ("fiscal_machine", "Fiscal Machine"),
        ],
        default="free_form",
    )
    # Habilita la acción "Generate TFHKA Digitalization Batch" en la lista de
    # facturas. Apagado por defecto: sin esto, tfhka.batch.service.create_batch
    # rechaza la operación aunque el usuario tenga el botón/acción visible.
    # Depende de digitalization_with_payment_tfhka: el lote encola directo
    # (sin pasar por el filtro "not payment-driven" de
    # account.move._tfhka_enqueue_eligible_for_digitalization), así que solo
    # tiene sentido habilitarlo cuando ese es el modo de la compañía. Esa
    # dependencia se aplica en res.config.settings (onchange + set_values,
    # mismo patrón que dispatch_guide_digital_tfhka) y se revalida en
    # tfhka.batch.service.create_batch -- NO con un @api.constrains aquí: los
    # campos `related` del wizard de Ajustes se escriben uno por uno (cada
    # inverse dispara su propio write()), así que una constraint cruzada entre
    # dos de ellos ve estados transitorios inconsistentes y aborta el guardado
    # incluso cuando el resultado final sería válido.
    batch_invoicing_tfhka = fields.Boolean(
        string="Batch Invoicing",
        default=False,
        help="Allows grouping several posted invoices into a TFHKA digitalization "
             "batch: reserves a numbering range via /AsignarNumeraciones and marks "
             "them with esLote before they go through the digitalization queue. "
             "Requires 'Digital invoicing with payment registration' to be enabled.",
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
            self.env["tfhka.api.client"]._log_call(
                self, "/Autenticacion", payload, None, None, str(e), False
            )
            raise ValidationError(_("Error connecting to the TFHKA API: %s", e))

    def _validate_tfhka_credentials(self):
        if not self.username_tfhka:
            raise UserError(_("You must register the Username for TFHKA."))
        if not self.password_tfhka:
            raise UserError(_("You must register the Password for TFHKA."))
        if not self.url_tfhka:
            raise UserError(_("You must register the URL for TFHKA."))
        _logger.info("TFHKA credentials validated successfully.")

    def _handle_tfhka_response(self, response, payload):
        data = response.json()
        success = response.status_code == 200 and data.get("codigo") == 200
        self.env["tfhka.api.client"]._log_call(
            self,
            "/Autenticacion",
            payload,
            None,
            response.status_code,
            json.dumps(
                self.env["tfhka.api.log"]._sanitize_payload(data), default=str, indent=2
            ),
            success,
        )
        if success:
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
            _logger.info("TFHKA token generated successfully.")
        else:
            _logger.error("The 'token' field is not found in the response: %s", data)
            raise ValidationError(_("TFHKA API response does not contain 'token'."))

    def _handle_tfhka_http_error(self, response, data):
        message = data.get("mensaje")
        if message:
            raise ValidationError(_("Authentication error: %(message)s") % {"message": message})
        else:
            raise ValidationError(_("Error in the TFHKA API: %(status_code)s") % {"status_code": response.status_code})