from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
from pytz import timezone
import logging
import requests
import json

_logger = logging.getLogger(__name__)

class EndPoints():
    BASE_ENDPOINTS = {
        "emision": "/Emision",
        "ultimo_documento": "/UltimoDocumento",
        "consulta_numeraciones": "/ConsultaNumeraciones",
    }

class AccountRetention(models.Model):
    _inherit = 'account.retention'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_retention_iva = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    show_digital_retention_islr = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)

    def get_base_url(self):
        if self.company_id.url_tfhka:
            return self.company_id.url_tfhka.rstrip("/")
        raise UserError(_("The URL is not configured in the company settings."))

    def get_token(self):
        if self.company_id.token_auth_tfhka:
            return self.company_id.token_auth_tfhka
        raise ValidationError(_("Configuration error: The authentication token is empty."))

    def call_tfhka_api(self, endpoint_key, payload):
        base_url = self.get_base_url()
        endpoint = EndPoints.BASE_ENDPOINTS.get(endpoint_key)

        if not endpoint:
            raise UserError(_("Endpoint '%(endpoint_key)s' is not defined.") % {'endpoint_key': endpoint_key})

        url = f"{base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.get_token()}"}

        try:
            response = requests.post(url, json=payload, headers=headers)
        
            if response.status_code == 200:
                data = response.json()
                if data.get("codigo") == "200":
                    return data
                elif data.get("codigo") == "203" and data.get("validaciones") and endpoint_key == "ultimo_documento":
                    return 0
                else:
                    _logger.error(_("Error in the API response: %(message)s \n%(validation)s") % {'message': data.get('mensaje'), 'validation': data.get('validaciones')})
                    raise UserError(_("Error in the API response: %(message)s \n%(validation)s") % {'message': data.get('mensaje'), 'validation': data.get('validaciones')})
            if response.status_code == 401:
                _logger.error(_("Error 401: Invalid or expired token."))
                self.company_id.generate_token_tfhka()
                return self.call_tfhka_api(endpoint_key, payload)
            else:
                _logger.error(_("HTTP error %(status_code)s: %(text)s") % {'status_code': response.status_code, 'text': response.text})
                raise UserError(_("HTTP error %(status_code)s: %(text)s") % {'status_code': response.status_code, 'text': response.text})
        except requests.exceptions.RequestException as e:
            _logger.error(_("Error connecting to the API: %(error)s") % {'error': e})
            raise UserError(_("Error connecting to the API: %(error)s") % {'error': e})

    def generate_document_digital(self):
        if not self.company_id.invoice_digital_tfhka:
            return
        if self.is_digitalized:
            raise UserError(_("The document has already been digitalized."))
        document_type = self.env.context.get('document_type')
        self.query_numbering()
        document_number = self.get_last_document_number(document_type)
        document_number = int(str(document_number)[6:]) + 1
        current_number = int(self.number[6:])
        validation_sequence = self.env.context.get('account_retention_alert', False)

        if document_number != current_number and not validation_sequence and self.company_id.sequence_validation_tfhka:
            message = _("The document sequence in Odoo (%s) does not match the sequence in The Factory (%s). Do you want to continue anyway?") % (current_number, document_number)
            return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.retention.alert.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_ve_invoice_digital.account_retention_alert_wizard').id,
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_message': message,
            }
        }

        document_number = str(self.number)

        self.generate_document_data(document_number, document_type, validation_sequence)
    
    def generate_document_data(self, document_number, document_type, validation_sequence):
        document_identification = self.get_document_identification(document_type, document_number)
        subject_retention = self.get_subject_retention()
        total_retention = self.get_total_retention(document_type)
        retention_details = self.get_retention_details(document_type)

        payload = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": document_identification,
                    "sujetoRetenido": subject_retention,
                    "totalesRetencion": total_retention
                },
                "detallesRetencion": retention_details,
            }
        }
        response = self.call_tfhka_api("emision", payload)

        if response:
            self.is_digitalized = True
            self.control_number_tfhka = response.get("resultado").get("numeroControl")
            emission_date = fields.Datetime.now().strftime("%d/%m/%Y")
            if validation_sequence:
                self.message_post(
                    body=_("Warning accepted: The difference in sequence between Odoo and The Factory is acknowledged and accepted."),  
                    message_type='comment',
                )
            self.message_post(
                body=_("Document successfully digitized on %(date)s") % {'date': emission_date},  
                message_type='comment',
            )

            return
    
    def get_last_document_number(self, document_type):
        payload = {
                    "serie": "",
                    "tipoDocumento": document_type,
                }
        response = self.call_tfhka_api("ultimo_documento", payload)
        
        if response == 0:
            return response
        else:
            document_number = response["numeroDocumento"] if response["numeroDocumento"] else response
            return document_number

    def query_numbering(self, series=""):
        payload={
                "serie": series,
                "tipoDocumento": "",
                "prefix": ""
            }
        response = self.call_tfhka_api("consulta_numeraciones", payload)

        if response:
            approves = False
            for numbering in response.get("numeraciones", []):
                if series != "":
                    if numbering.get("serie") == series:
                        end_number = numbering.get("hasta")
                        start_number = numbering.get("correlativo")
                else:
                    if numbering.get("serie") == "NO APLICA":
                        end_number = numbering.get("hasta")
                        start_number = numbering.get("correlativo")
                
                if int(start_number) < int(end_number):
                    approves = True
                    break

            if approves:
                return

            raise UserError(_("The numbering range is exhausted. Please contact the administrator."))

    def get_document_identification(self, document_type, document_number):
        for record in self:
            now = fields.Datetime.now()
            emission_time = now.astimezone(timezone(record.env.user.tz)).strftime("%I:%M:%S %p").lower()
            emission_date = now.strftime("%d/%m/%Y")
            affected_invoice_number = ""

            for line in record.retention_line_ids:
                prefix = ""
                if line.move_id.debit_origin_id:
                    affected_invoice_number = str(line.move_id.debit_origin_id.sequence_number)

                if line.move_id.reversed_entry_id:
                    affected_invoice_number = str(line.move_id.reversed_entry_id.sequence_number)

            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "numeroFacturaAfectada":affected_invoice_number,
                "fechaEmision": emission_date,
                "horaEmision": emission_time,
                "serie": "",
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": record.company_id.currency_id.name,
            }
    
    def get_subject_retention(self):
        for record in self:
            if record.partner_id:
                partner_data = {}
                if not record.partner_id.vat:
                    raise UserError(_("The 'NIF' field of the Customer cannot be empty for digitalization."))

                vat = record.partner_id.vat.upper()

                if vat[0].isalpha(): 
                    partner_data["tipoIdentificacion"] = vat[0]
                    partner_data["numeroIdentificacion"] = vat[1:]
                else:
                    partner_data["tipoIdentificacion"] = ""
                    partner_data["numeroIdentificacion"] = vat

                if record.partner_id.prefix_vat:
                    partner_data["tipoIdentificacion"] = record.partner_id.prefix_vat

                partner_data["numeroIdentificacion"] = partner_data["numeroIdentificacion"].replace("-", "").replace(".", "")
                partner_data["razonSocial"] = record.partner_id.name
                partner_data["direccion"] = record.partner_id.street or "no definida"
                partner_data["pais"] = record.partner_id.country_code
                partner_data["telefono"] = record.partner_id.mobile or record.partner_id.phone
                partner_data["correo"]= record.partner_id.email

                if not record.partner_id.country_code:
                    raise UserError(_("The 'Country' field of the Customer cannot be empty for digitalization."))

                if not (record.partner_id.mobile or record.partner_id.phone):
                    raise UserError(_("The 'Mobile' field of the Customer cannot be empty for digitalization."))

                if not record.partner_id.email:
                    raise UserError(_("The 'Email' field of the Customer cannot be empty for digitalization."))

                return {
                    "tipoIdentificacion": partner_data["tipoIdentificacion"],
                    "numeroIdentificacion": partner_data["numeroIdentificacion"],
                    "razonSocial": partner_data["razonSocial"],
                    "direccion": partner_data["direccion"],
                    "pais": partner_data["pais"],
                    "telefono": [partner_data["telefono"]],
                    "notificar": "Si",
                    "correo": [partner_data["correo"]],
                }
        return None
    
    def get_total_retention(self, document_type):
        retention_data = {}

        for record in self:
            retention_data = {
                "totalBaseImponible": str(round(abs(record.total_invoice_amount), 2)), 
                "numeroCompRetencion": record.number, 
                "fechaEmisionCR": record.date.strftime("%d/%m/%Y"), 
                "tipoComprobante": "" if record.total_iva_amount else "1",
            }
            if document_type == "05":
                retention_data["totalRetenido"] = str(round(abs(record.total_retention_amount), 2))
                retention_data["totalIVA"] = str(round(abs(record.total_iva_amount), 2))
            else:
                retention_data["TotalISRL"] = str(round(abs(record.total_iva_amount), 2))

            return retention_data    

    def get_retention_details(self, document_type):
        retention_details = []
        type_document = {
            "in_invoice": "01",
            "in_refund": "02",
        }
        
        counter = 1
        for record in self:
            for line in record.retention_line_ids:
                tipo_documento = type_document.get(line.move_id.move_type, "03") if not line.move_id.debit_origin_id else "03"
                document_number_ret = str(line.move_id.sequence_number)

                retention_data = {
                    "numeroLinea": str(counter), 
                    "fechaDocumento": line.date_accounting.strftime("%d/%m/%Y"), 
                    "tipoDocumento": tipo_documento,
                    "numeroDocumento": document_number_ret,
                    "numeroControl": line.move_id.correlative,
                    "montoTotal": str(round(line.invoice_total, 2)),  
                    "baseImponible": str(round(line.invoice_amount, 2)),
                    "moneda": record.company_id.currency_id.name,
                    "retenido": str(round(line.retention_amount, 2)),
                }

                if document_type == "05":
                    retention_data["montoIVA"] = str(round(line.iva_amount, 2))
                    retention_data["porcentaje"] = str(round(line.aliquot, 2))
                    retention_data["retenidoIVA"] = str(round(line.related_percentage_tax_base, 2))

                if document_type == "06":
                    code = line.code
                    if code:
                        retention_data["CodigoConcepto"] = code.zfill(3)

                    retention_data["porcentaje"] = str(round(line.related_percentage_fees, 2))

                retention_details.append(retention_data)
                counter += 1

        return retention_details

    @api.depends('state', 'is_digitalized')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_retention_iva = True
            record.show_digital_retention_islr = True
            if record.state =='emitted' and not record.is_digitalized and record.company_id.invoice_digital_tfhka:
                record.show_digital_retention_iva = False
                record.show_digital_retention_islr = False
