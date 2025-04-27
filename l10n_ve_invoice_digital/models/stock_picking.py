from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
import logging
import requests
import re
import json

_logger = logging.getLogger(__name__)

class EndPoints():
    BASE_ENDPOINTS = {
        "emision": "/Emision",
        "ultimo_documento": "/UltimoDocumento",
        "asignar_numeraciones": "/AsignarNumeraciones",
        "consulta_numeraciones": "/ConsultaNumeraciones",
    }

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_dispatch_guide = fields.Boolean(string="Show Digital Dispatch Guide", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)

    def generate_document_digtal(self):
        if self.is_digitalized:
            raise UserError(_("The document has already been digitalized."))
        document_type = self.env.context.get('document_type')
        end_number, start_number = self.query_numbering()
        document_number = self.get_last_document_number(document_type)
        document_number = str(document_number + 1)

        if document_number == start_number:
            self.assign_numbering(end_number, start_number)

        self.generate_document_data(document_number, document_type)

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
                    _logger.error(_("Error in the API response: %(message)s") % {'message': data.get('mensaje')})
                    raise UserError(_("Error in the API response: %(message)s") % {'message': data.get('mensaje')})
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

    def generate_document_data(self, document_number, document_type):
        document_identification = self.get_document_identification(document_type, document_number)
        buyer = self.get_buyer()
        details_items = self.get_item_details()
        dispatch_guide = self.get_dispatch_guide()

        payload = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": document_identification,
                    "comprador": buyer,
                },
                "detallesItems": details_items,
                'guiaDespacho': dispatch_guide,
            }
        }

        response = self.call_tfhka_api("emision", payload)

        if response:
            self.control_number_tfhka = response.get("resultado").get("numeroControl")
            self.is_digitalized = True
            self.message_post(
                body=_("Document successfully digitized"),  
                message_type='comment',
            )

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
                        "tipoDocumento": "01",
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
            emission_time = record.sale_id.date_order.strftime("%I:%M:%S %p").lower() if record.sale_id.date_order else ""
            emission_date = record.sale_id.date_order.strftime("%d/%m/%Y") if record.sale_id.date_order else ""
            due_date = record.sale_id.validity_date.strftime("%d/%m/%Y") if record.sale_id.validity_date else ""
            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "fechaEmision": emission_date,
                "fechaVencimiento": due_date,
                "horaEmision": emission_time,
                "tipoDePago": self.get_payment_type(),
                "serie": "",
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": record.sale_id.currency_id.name,
                "transaccionId": "",
                "urlPdf": ""
            }

    def get_item_details(self):
        item_details = []
        line_number = 1
        for record in self:
            for line in record.sale_id.order_line:
                tax_mapping = {
                    0.0: "E",
                    8.0: "R",
                    16.0: "G",
                    31.0: "A",
                }
                taxes = line.tax_id.filtered(lambda t: t.amount)
                tax_rate = taxes[0].amount if taxes else 0.0

                item_details.append({
                    "numeroLinea": str(line_number),
                    "codigoPLU": line.product_id.barcode or line.product_id.default_code or "",
                    "indicadorBienoServicio": "2" if line.product_id.type == 'service' else "1",
                    "descripcion": line.product_id.name,
                    "cantidad": str(line.product_uom_qty),
                    "precioUnitario": str(round(line.price_unit, 2)),
                    "precioItem": str(round(line.price_total, 2)),
                    "codigoImpuesto": tax_mapping[tax_rate],
                    "tasaIVA": str(round(line.tax_id.amount, 2)),
                    "valorIVA": str(round(line.price_total - line.price_subtotal, 2)),
                    "valorTotalItem": str(round(line.price_total, 2)),
                })
                line_number += 1
        return item_details

    def get_buyer(self):
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
                partner_data["direccion"] = record.partner_id.contact_address_complete or "no definida"
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

    def get_payment_type(self):
        for record in self.sale_id:
            if record.payment_term_id.line_ids.nb_days > 0:
                return "Crédito"
            else:
                return "Inmediato"

    def get_dispatch_guide(self):
        for record in self:
            product_origin_set = set()
            product_origin = ""

            for line in record.sale_id.order_line:
                if line.product_id.country_of_origin.name:
                    if line.product_id.country_of_origin.name == self.company_id.country_id.name:
                        product_origin_set.add("Nacional")
                    else:
                        product_origin_set.add("Importado")
                    if len(product_origin_set) > 1:
                        break
                            
            product_origin = "Nacional e Importado" if len(product_origin_set) > 1 else (product_origin_set.pop() if product_origin_set else "Sin origen definido")
            weight = f"{record.shipping_weight:.2f} {record.weight_uom_name}" if record.shipping_weight else "Sin peso"
            description = re.sub(r'<.*?>', '', str(record.note)) if record.note else "Sin descripción"
            destination = record.partner_id.contact_address_complete or "no definida"

            return {
                "esGuiaDespacho": "1",
                "motivoTraslado": record.transfer_reason_id.name,
                "descripcionServicio": description,
                "tipoProducto": "Sin especificar",
                "origenProducto": product_origin,
                "pesoOVolumenTotal": weight,
                "destinoProducto": destination,
            }

    @api.depends('state', 'is_digitalized', 'dispatch_guide_controls')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_dispatch_guide = True
            if record.state == "done" and not record.is_digitalized and record.company_id.invoice_print_type == "digital":
                if record.dispatch_guide_controls:
                    record.show_digital_dispatch_guide = False
