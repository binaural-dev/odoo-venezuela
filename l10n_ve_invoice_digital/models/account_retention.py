from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
import logging
import requests
import json

_logger = logging.getLogger(__name__)

class EndPoints():
    BASE_ENDPOINTS = {
        "emision": "/Emision",
        "ultimo_documento": "/UltimoDocumento",
        "asignar_numeraciones": "/AsignarNumeraciones",
        "consulta_numeraciones": "/ConsultaNumeraciones",
    }

class AccountRetention(models.Model):
    _inherit = 'account.retention'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False)
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
        if self.is_digitalized:
            raise UserError(_("The document has already been digitalized."))
        document_type = self.env.context.get('document_type')
        end_number, start_number = self.query_numbering()
        document_number = self.get_last_document_number(document_type)
        document_number = str(document_number + 1)

        if document_number == start_number:
            self.assign_numbering(end_number, start_number)

        self.generate_document_data(document_number, document_type)
    
    def generate_document_data(self, document_number, document_type):
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

    def assign_numbering(self, end_number, start_number):
        end = start_number + self.company_id.range_assignment_tfhka
        start_number += 1
        
        if start_number <= end_number:
            payload = {
                        "serie": "",
                        "tipoDocumento": "05",
                        "numeroDocumentoInicio": start_number,
                        "numeroDocumentoFin": end
                    }
            response = self.call_tfhka_api("asignar_numeraciones", payload)
            
            if response:
                _logger.info("Numbering range successfully assigned.")

    def query_numbering(self):
        payload={
                "serie": "",
                "tipoDocumento": "",
                "prefix": ""
            }
        response = self.call_tfhka_api("consulta_numeraciones", payload)

        if response:
            numbering = response["numeraciones"][0]
            end_number = numbering.get("hasta")
            start_number = numbering.get("correlativo")
            return end_number, start_number

    def get_document_identification(self, document_type, document_number):
        for record in self:
            emission_time = record.create_date.strftime("%I:%M:%S %p").lower()
            emission_date = record.date_accounting.strftime("%d/%m/%Y") if record.date_accounting else ""
            affected_invoice_number = ""
            subsidiary = ""

            for line in record.retention_line_ids:
                if line.move_id.debit_origin_id:
                    affected_invoice_number = line.move_id.debit_origin_id.name
                    prefix = line.move_id.debit_origin_id.journal_id.sequence_id.prefix

                if line.move_id.reversed_entry_id:
                    affected_invoice_number = line.move_id.reversed_entry_id.name
                    prefix = line.move_id.reversed_entry_id.journal_id.sequence_id.prefix

                if prefix and affected_invoice_number.startswith(prefix):
                    affected_invoice_number = affected_invoice_number[len(prefix):]

            if self.company_id.subsidiary:
                if record.account_analytic_id and record.account_analytic_id.code:
                    subsidiary = record.account_analytic_id.code
                else:
                    raise UserError(_("The selected subsidiary does not contain a reference"))

            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "numeroFacturaAfectada":affected_invoice_number,
                "fechaEmision": emission_date,
                "horaEmision": emission_time,
                "serie": "",
                "sucursal": subsidiary,
                "tipoDeVenta": "Interna",
                "moneda": self.company_id.currency_id.name,
            }
    
    def get_subject_retention(self):
        for record in self:
            if record.partner_id:
                partner_data = {}
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
                document_number_ret = line.move_id.name
                prefix = line.move_id.journal_id.sequence_id.prefix

                if prefix and document_number_ret.startswith(prefix):
                    document_number_ret = document_number_ret[len(prefix):]

                retention_data = {
                    "numeroLinea": str(counter), 
                    "fechaDocumento": line.date_accounting.strftime("%d/%m/%Y"), 
                    "tipoDocumento": tipo_documento,
                    "numeroDocumento": document_number_ret,
                    "numeroControl": line.move_id.correlative,
                    "montoTotal": str(round(line.invoice_total, 2)),  
                    "baseImponible": str(round(line.invoice_amount, 2)),
                    "moneda": self.company_id.currency_id.name,
                    "retenido": str(round(line.retention_amount, 2)),
                }

                if document_type == "05":
                    retention_data["montoIVA"] = str(round(line.iva_amount, 2))
                    retention_data["porcentaje"] = str(round(line.aliquot, 2))
                    retention_data["retenidoIVA"] = str(round(line.related_percentage_tax_base, 2))

                if document_type == "06":
                    for concept_line in line.payment_concept_id.line_payment_concept_ids:
                        if record.partner_id.type_person_id.id == concept_line.id:
                            retention_data["CodigoConcepto"] = concept_line.code
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
