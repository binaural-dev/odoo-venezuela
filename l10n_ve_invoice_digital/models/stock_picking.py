from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
from pytz import timezone
import logging
import requests
import re
import json

_logger = logging.getLogger(__name__)

DOCUMENT_TYPE = "04"

class EndPoints():
    BASE_ENDPOINTS = {
        "emision": "/Emision",
        "ultimo_documento": "/UltimoDocumento",
        "consulta_numeraciones": "/ConsultaNumeraciones",
    }

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_dispatch_guide = fields.Boolean(string="Show Digital Dispatch Guide", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for record in self:
            if record.company_id.invoice_digital_tfhka and not record.is_digitalized and (record.dispatch_guide_controls or record.is_dispatch_guide):
                record.generate_document_digital() 
        return res

    def generate_document_digital(self):
        if self.is_digitalized:
            raise UserError(_("The document has already been digitalized.")) 
        self.query_numbering()
        document_number = self.get_last_document_number(DOCUMENT_TYPE)
        document_number = str(document_number + 1)

        self.generate_document_data(document_number, DOCUMENT_TYPE)

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

    def generate_document_data(self, document_number, document_type):
        document_identification = self.get_document_identification(document_type, document_number)
        buyer = self.get_buyer()
        details_items = self.get_item_details()
        dispatch_guide = self.get_dispatch_guide()
        additional_information = self.get_additional_information()

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

        if additional_information:
            payload["documentoElectronico"]["infoAdicional"] = additional_information

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
                current_series = (numbering.get("serie") or "").upper()
                if series != "":
                    if current_series == series.upper():
                        end_number = numbering.get("hasta")
                        start_number = numbering.get("correlativo")
                else:
                    if current_series == "NO APLICA":
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
            due_date = record.date_deadline.strftime("%d/%m/%Y") if record.date_deadline else emission_date

            subsidiary = ""

            if self.company_id.subsidiary:
                if record.subsidiary_origin_id and record.subsidiary_origin_id.code:
                    subsidiary = record.subsidiary_origin_id.code
                else:
                    raise UserError(_("The selected subsidiary does not contain a reference"))

            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "fechaEmision": emission_date,
                "fechaVencimiento": due_date,
                "horaEmision": emission_time,
                "tipoDePago": self.get_payment_type(),
                "serie": "",
                "sucursal": subsidiary,
                "tipoDeVenta": "Interna",
                "moneda": "VEF",
                "transaccionId": "",
                "urlPdf": ""
            }

    def get_item_details(self):
        item_details = []
        line_number = 1
        for record in self:
            if record.sale_id and record.transfer_reason_id.code == "sale":
                for line in record.sale_id.order_line:
                    tax_mapping = {
                        0.0: "E",
                        8.0: "R",
                        16.0: "G",
                        31.0: "A",
                    }
                    taxes = line.tax_id.filtered(lambda t: t.amount)
                    tax_rate = taxes[0].amount if taxes else 0.0
                    
                    if record.sale_id.currency_id.name == "VEF":
                        unit_price = round(line.price_unit, 2)
                        item_price = round(line.price_total, 2)
                    else:
                        unit_price = round(line.foreign_price, 2)
                        item_price = round(line.foreign_subtotal, 2)
                        
                    vat = round(item_price * line.tax_id.amount / 100, 2)
                    total_item_value = round(item_price + vat, 2)
                            
                    item_details.append({
                        "numeroLinea": str(line_number),
                        "codigoPLU": line.product_id.barcode or line.product_id.default_code or "",
                        "indicadorBienoServicio": "2" if line.product_id.type == 'service' else "1",
                        "descripcion": line.product_id.name,
                        "cantidad": str(line.product_uom_qty),
                        "precioUnitario": str(unit_price),
                        "precioItem": str(item_price),
                        "codigoImpuesto": tax_mapping[tax_rate],
                        "tasaIVA": str(round(line.tax_id.amount, 2)),
                        "valorIVA": str(vat),
                        "valorTotalItem": str(total_item_value),
                    })
                    line_number += 1
            else:
                for line in record.move_ids_without_package:
                    item_details.append({
                        "numeroLinea": str(line_number),
                        "codigoPLU": line.product_id.barcode or line.product_id.default_code or "",
                        "indicadorBienoServicio": "2" if line.product_id.type == 'service' else "1",
                        "descripcion": line.product_id.name,
                        "cantidad": str(line.product_uom_qty),
                        "precioUnitario": "0",
                        "precioItem": "0",
                        "tasaIVA": "0",
                        "valorIVA": "0",
                        "valorTotalItem": "0",
                    })
                    line_number += 1
        return item_details

    def get_buyer(self):
        for record in self:
            if record.partner_id:
                partner = record.partner_id
                if partner.parent_id:
                    partner = record.partner_id.parent_id

                partner_data = {}
                vat = partner.vat.upper()

                if vat[0].isalpha(): 
                    partner_data["tipoIdentificacion"] = vat[0]
                    partner_data["numeroIdentificacion"] = vat[1:]
                else:
                    partner_data["tipoIdentificacion"] = ""
                    partner_data["numeroIdentificacion"] = vat

                if partner.prefix_vat:
                    partner_data["tipoIdentificacion"] = partner.prefix_vat

                partner_data["numeroIdentificacion"] = partner_data["numeroIdentificacion"].replace("-", "").replace(".", "")
                partner_data["razonSocial"] = partner.name
                partner_data["direccion"] = partner.contact_address_complete or "no definida"
                partner_data["pais"] = partner.country_code
                partner_data["telefono"] = partner.mobile or partner.phone
                partner_data["correo"]= partner.email

                if not partner.country_code:
                    raise UserError(_("The 'Country' field of the Customer cannot be empty for digitalization."))

                if not (partner.mobile or partner.phone):
                    raise UserError(_("The 'Mobile' field of the Customer cannot be empty for digitalization."))

                if not partner.email:
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
            if record.transfer_reason_id.code == "other_causes":
                transfer_reason = record.other_causes_transfer_reason
            else:
                transfer_reason = record.transfer_reason_id.name

            return {
                "esGuiaDespacho": "1",
                "motivoTraslado": transfer_reason,
                "descripcionServicio": description,
                "tipoProducto": "Sin especificar",
                "origenProducto": product_origin,
                "pesoOVolumenTotal": weight,
            }

    def get_additional_information(self):
        additional_information = []
        for record in self:
            if record.partner_id:
                additional_information.append({
                    "campo": "direccionEntrega",
                    "valor": record.partner_id.contact_address_complete or "no definida",
                })
        return additional_information

    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_dispatch_guide = True
            if record.company_id.invoice_digital_tfhka:
                record.show_digital_dispatch_guide = False
