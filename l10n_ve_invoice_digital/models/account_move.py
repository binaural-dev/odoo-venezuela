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

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_invoice = fields.Boolean(string="Show Digital Invoice", compute="_compute_visibility_button", copy=False)
    show_digital_debit_note = fields.Boolean(string="Show Digital Note Debit", compute="_compute_visibility_button", copy=False)
    show_digital_credit_note = fields.Boolean(string="Show Digital Note Credit", compute="_compute_visibility_button", copy=False)

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for record in self:
            if record.name == '/':
                last_invoice = self.env['account.move'].search(
                    [
                        ('move_type', 'in', ['out_invoice', 'out_refund']),
                        ('name', '!=', '/')
                    ], order='create_date desc', limit=1
                )
                if not last_invoice.name:
                    continue
                if not last_invoice.is_digitalized:
                    selection_dict = dict(last_invoice._fields['move_type'].selection)
                    move_type_name = selection_dict.get(last_invoice.move_type)
                    raise ValidationError(
                        _("The %(move_type_name)s %(invoice_name)s has not been digitalized yet.\n"
                            "Please complete the digitalization process before proceeding.") % {
                            'move_type_name': move_type_name,
                            'invoice_name': last_invoice.name
                        }
                    )
        return res

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
        seller = self.get_seller()
        buyer = self.get_buyer()
        totals, foreign_totals = self.get_totals()
        details_items = self.get_item_details()

        payload = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": document_identification,
                    "comprador": buyer,
                    "totales": totals,
                },
                "detallesItems": details_items,
            }
        }
        if seller:
            payload["documentoElectronico"]["encabezado"]["vendedor"] = seller
        if foreign_totals:
            payload["documentoElectronico"]["encabezado"]["totalesOtraMoneda"] = foreign_totals

        response = self.call_tfhka_api("emision", payload)

        if response:
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
            emission_time = record.create_date.strftime("%I:%M:%S %p").lower()
            affected_invoice_number = ""
            affected_invoice_date = ""
            affected_invoice_amount = ""
            affected_invoice_comment = ""

            if record.debit_origin_id:
                affected_invoice_number = record.debit_origin_id.name
                affected_invoice_date = record.debit_origin_id.invoice_date.strftime("%d/%m/%Y") if record.debit_origin_id.invoice_date else ""

                if record.currency_id.name == "VEF":
                    affected_invoice_amount = str(record.debit_origin_id.amount_total)
                else:
                    tax_totals = record.debit_origin_id.tax_totals
                    affected_invoice_amount = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                part = record.ref.split(',')
                affected_invoice_comment = part[1].strip()

            if record.reversed_entry_id:
                affected_invoice_number = record.reversed_entry_id.name
                affected_invoice_date = record.reversed_entry_id.invoice_date.strftime("%d/%m/%Y") if record.reversed_entry_id.invoice_date else ""

                if record.currency_id.name == "VEF":
                    affected_invoice_amount = str(record.reversed_entry_id.amount_total)
                else:
                    tax_totals = record.reversed_entry_id.tax_totals
                    affected_invoice_amount = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                part = record.ref.split(',')
                affected_invoice_comment = part[1].strip()

            emission_date = record.invoice_date.strftime("%d/%m/%Y") if record.invoice_date else ""
            due_date = record.invoice_date_due.strftime("%d/%m/%Y") if record.invoice_date_due else ""
            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "numeroPlanillaImportacion": "",
                "numeroExpedienteImportacion": "",
                "serieFacturaAfectada": "",
                "numeroFacturaAfectada": affected_invoice_number,
                "fechaFacturaAfectada": affected_invoice_date,
                "montoFacturaAfectada": affected_invoice_amount,
                "comentarioFacturaAfectada": affected_invoice_comment,
                "regimenEspTributacion": "",
                "fechaEmision": emission_date,
                "fechaVencimiento": due_date,
                "horaEmision": emission_time,
                "tipoDePago": self.get_payment_type(),
                "serie": "",
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": record.currency_id.name,
                "transaccionId": "",
                "urlPdf": ""
            }

    def get_totals(self):
        for record in self:
            currency = record.currency_id.name
            totalIGTF = 0
            totalIGTF_VES = 0
            tax_totals = record.tax_totals

            totalIGTF = round(tax_totals.get("igtf", {}).get("igtf_amount", 0), 2)
            totalIGTF_VES = round(tax_totals.get("igtf", {}).get("foreign_igtf_amount", 0), 2)
            amounts = {}
            amounts_foreign = {}

            if currency == "VEF":
                amounts["montoGravadoTotal"] = str(
                    round(
                        tax_totals.get('subtotal', 0) - 
                        next(
                            (group['tax_group_base_amount'] for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') == "Exento"), 0
                        ), 2
                    )
                )
                amounts["montoExentoTotal"] = str(
                    round(
                        next((
                            group.get('tax_group_base_amount', 0) 
                            for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') == "Exento"
                        ), 0), 2)
                )
                amounts["subtotal"] = str(round(tax_totals.get("amount_untaxed", 0), 2))
                amounts["subtotalAntesDescuento"] = str(round(tax_totals.get('subtotal', 0), 2))
                amounts["totalAPagar"] = str(round(tax_totals.get("amount_total_igtf", 0), 2))
                amounts["totalIVA"] = round(sum(group.get('tax_group_amount', 0) for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])), 2)
                amounts["montoTotalConIVA"] = str(round(tax_totals.get("amount_total", 0), 2))
                amounts["totalDescuento"] = str(abs(round(tax_totals.get("discount_amount", 0), 2)))
                
                taxes_subtotal = self.get_tax_subtotals(currency)

            else:
                amounts_foreign["montoGravadoTotal"] = str(
                    round(
                        tax_totals.get('subtotal', 0) - 
                        next(
                            (group['tax_group_base_amount'] for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') == "Exento"), 0
                        ), 2
                    )
                )
                amounts_foreign["montoExentoTotal"] = str(
                    round(
                        next((
                            group.get('tax_group_base_amount', 0) 
                            for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') == "Exento"
                        ), 0), 2)
                )
                amounts_foreign["subtotal"] = str(round(tax_totals.get("amount_untaxed", 0), 2))
                amounts_foreign["subtotalAntesDescuento"] = str(round(tax_totals.get('subtotal', 0), 2))
                amounts_foreign["totalAPagar"] = str(round(tax_totals.get("amount_total_igtf", 0), 2))
                amounts_foreign["totalIVA"] = round(sum(group.get('tax_group_amount', 0) for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])), 2)
                amounts_foreign["montoTotalConIVA"] = str(round(tax_totals.get("amount_total", 0), 2))
                amounts_foreign["totalDescuento"] = str(abs(round(tax_totals.get("discount_amount", 0), 2)))

                amounts["montoGravadoTotal"] = str(
                    round(
                        tax_totals.get('foreign_subtotal', 0) - 
                        next(
                            (group['tax_group_base_amount'] for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') == "Exento"), 0
                        ), 2
                    )
                )
                amounts["montoExentoTotal"] = str(
                    round(
                        next((
                            group.get('tax_group_base_amount', 0) 
                            for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') == "Exento"
                        ), 0), 2)
                )
                amounts["subtotal"] = str(round(tax_totals.get("foreign_amount_untaxed", 0), 2))
                amounts["subtotalAntesDescuento"] = str(round(tax_totals.get("foreign_subtotal", 0), 2))
                amounts["totalAPagar"] = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))
                amounts["totalIVA"] = round(sum(group.get('tax_group_amount', 0) for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])), 2)
                amounts["montoTotalConIVA"] = str(round(tax_totals.get("foreign_amount_total", 0), 2))
                amounts["totalDescuento"] = str(abs(round(tax_totals.get("foreign_discount_amount", 0), 2)))
                
                taxes_subtotal, taxes_subtotal_foreign = self.get_tax_subtotals(currency)

            totals = {
                "nroItems": str(len(record.invoice_line_ids)),
                "montoGravadoTotal": amounts["montoGravadoTotal"],
                "montoExentoTotal": amounts["montoExentoTotal"],
                "subtotal": amounts["subtotal"],
                "subtotalAntesDescuento": amounts["subtotalAntesDescuento"],
                "totalAPagar": amounts["totalAPagar"],
                "totalIVA": str(amounts["totalIVA"]),
                "montoTotalConIVA": amounts["montoTotalConIVA"],
                "totalDescuento": amounts["totalDescuento"],
                "impuestosSubtotal": taxes_subtotal,
                "totalIGTF": str(totalIGTF),
                "totalIGTF_VES": str(totalIGTF_VES),
            }
            payment_forms = self.get_payment_methods()

            if payment_forms:
                totals["formasPago"] = payment_forms

            if amounts_foreign:
                foreign_totals = {
                    "moneda": record.currency_id.name,
                    "tipoCambio": str(record.foreign_rate),
                    "montoGravadoTotal": amounts_foreign["montoGravadoTotal"],
                    "montoExentoTotal": amounts_foreign["montoExentoTotal"],
                    "subtotal": amounts_foreign["subtotal"],
                    "subtotalAntesDescuento": amounts_foreign["subtotalAntesDescuento"],
                    "totalAPagar": amounts_foreign["totalAPagar"],
                    "totalIVA": str(amounts_foreign["totalIVA"]),
                    "montoTotalConIVA": amounts_foreign["montoTotalConIVA"],
                    "totalDescuento": amounts_foreign["totalDescuento"],
                    "totalIGTF": str(totalIGTF),
                    "totalIGTF_VES": str(totalIGTF_VES),
                    "impuestosSubtotal": taxes_subtotal_foreign,
                }
            else:
                foreign_totals = False
        return totals, foreign_totals

    def get_tax_subtotals(self, currency):
        tax_subtotals = []
        tax_subtotals_foreign = []
        tax_code = {
            "IVA 8%": "R",
            "IVA 16%": "G",
            "IVA 31%": "A",
            "Exento": "E",
        }
        tax_rate = {
            "IVA 8%": "8.0",
            "IVA 16%": "16.0",
            "IVA 31%": "31.0",
            "Exento": "0.0",
            "3.0 %": "3.0"
        }
        for record in self:
            if currency == "VEF":
                for tax_totals in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    tax_subtotals.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    })
                return tax_subtotals
            else:
                for tax_totals in record.tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', []):
                    tax_subtotals.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    })
                for tax_totals in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    tax_subtotals_foreign.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    })
                if record.tax_totals.get('igtf', {}).get('apply_igtf'):
                    igtf = record.tax_totals.get('igtf', {})
                    tax_subtotals_foreign.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax_rate[igtf.get('name')],
                        "baseImponibleImp": str(round(igtf.get('igtf_base_amount'), 2)),
                        "valorTotalImp": str(round(igtf.get('igtf_amount'), 2)),
                    })
                    tax_subtotals.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax_rate[igtf.get('name')],
                        "baseImponibleImp": str(round(igtf.get('foreign_igtf_base_amount'), 2)),
                        "valorTotalImp": str(round(igtf.get('foreign_igtf_amount'), 2)),
                    })
                return tax_subtotals, tax_subtotals_foreign

    def get_item_details(self):
        item_details = []
        line_number = 1
        for record in self:
            for line in record.invoice_line_ids:
                tax_mapping = {
                    0.0: "E",
                    8.0: "R",
                    16.0: "G",
                    31.0: "A",
                }
                taxes = line.tax_ids.filtered(lambda t: t.amount)
                tax_rate = taxes[0].amount if taxes else 0.0

                item_details.append({
                    "numeroLinea": str(line_number),
                    "codigoPLU": line.product_id.barcode or line.product_id.default_code or "",
                    "indicadorBienoServicio": "2" if line.product_id.type == 'service' else "1",
                    "descripcion": line.product_id.name,
                    "cantidad": str(line.quantity),
                    "precioUnitario": str(round(line.price_unit, 2)),
                    "precioUnitarioDescuento": str(round(line.price_unit * (line.discount / 100), 2)),
                    "descuentoMonto": str(round((line.price_unit * (line.discount / 100)) * line.quantity, 2)),
                    "precioItem": str(round(line.price_subtotal, 2)),
                    "precioAntesDescuento": str(round(line.price_unit * line.quantity, 2)),
                    "codigoImpuesto": tax_mapping[tax_rate],
                    "tasaIVA": str(round(line.tax_ids.amount, 2)),
                    "valorIVA": str(round(line.price_total - line.price_subtotal, 2)),
                    "valorTotalItem": str(round(line.price_subtotal, 2)),
                })
                line_number += 1
        return item_details

    def get_seller(self):
        for record in self:
            if "seller_id" in record._fields and record.seller_id:
                return {
                    "codigo": str(record.seller_id.id),
                    "nombre": record.seller_id.name,
                    "numCajero": ""
                }
            else:
                return False

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

    def get_payment_type(self):
        for record in self:
            if record.invoice_payment_term_id.line_ids.nb_days > 0:
                return "Crédito"
            else:
                return "Inmediato"

    def get_payment_methods(self):
        try:
            payment_data = []
            for record in self:
                content_data = record.invoice_payments_widget.get("content", [])
                if content_data:
                    for item in content_data:
                        payment_method = self.get_payment_method(item)
                        currency = self.get_currency(item.get('currency_id'))
                        payment = self.get_payment(item.get('account_payment_id'))

                        if not payment:
                            continue
                        
                        payment_info = self.build_payment_info(item, payment, currency, payment_method, record.foreign_rate)
                        payment_data.append(payment_info)                    
                    return payment_data
            return False
        except Exception as e:
            _logger.error(f"Error processing payment methods: {e}")
            return False

    def get_payment_method(self, item):
        if item.get("payment_method_name") == "Efectivo":
            return "08" if self.get_currency(item.get('currency_id')) == "VES" else "09"
        elif item.get("payment_method_name") == "Transferencia":
            return "03"
        elif item.get("payment_method_name") == "Manual":
            return "99"
        return ""

    def get_currency(self, currency_id):
        currency_data = self.env['res.currency'].search([('id', '=', currency_id)])
        return currency_data.name if currency_data else ""

    def get_payment(self, account_payment_id):
        return self.env['account.payment'].search([('id', '=', account_payment_id)])

    def build_payment_info(self, item, payment, currency, payment_method, foreign_rate):
        payment_info = {
            "descripcion": payment.concept,
            "fecha": item.get("date").strftime("%d/%m/%Y") if item.get("date") else "",
            "forma": payment_method,
            "monto": str(item.get("amount")),
            "moneda": currency,
        }

        if currency != "VES":
            payment_info["tipoCambio"] = str(round(foreign_rate, 2))

        return payment_info

    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'is_digitalized', 'move_type')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_invoice = True
            record.show_digital_debit_note = True
            record.show_digital_credit_note = True
            
            if record.state == "posted" and not record.is_digitalized and record.company_id.invoice_digital_tfhka:
                if record.move_type == "out_refund" and record.reversed_entry_id and record.reversed_entry_id.is_digitalized:
                    record.show_digital_credit_note = False

                elif record.debit_origin_id and record.debit_origin_id.is_digitalized:
                    record.show_digital_debit_note = False

                elif record.move_type == "out_invoice" and not record.debit_origin_id:
                    record.show_digital_invoice = False
