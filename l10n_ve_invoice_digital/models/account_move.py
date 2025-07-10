from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
from pytz import timezone
import logging
import requests
import json
import re

_logger = logging.getLogger(__name__)

class EndPoints():
    BASE_ENDPOINTS = {
        "emision": "/Emision",
        "ultimo_documento": "/UltimoDocumento",
        "consulta_numeraciones": "/ConsultaNumeraciones",
    }

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_invoice = fields.Boolean(string="Show Digital Invoice", compute="_compute_invisible_check", copy=False)

    def generate_document_digital(self):
        if not self.company_id.invoice_digital_tfhka:
            return
        
        document_type = ""

        if self.move_type == "out_invoice":
            document_type = "03" if self.debit_origin_id else "01"
        elif self.move_type == "out_refund" and self.reversed_entry_id:
            document_type = "02"
        
        if not document_type: 
            return

        series = ""

        if self.company_id.group_sales_invoicing_series and self.journal_id.series_correlative_sequence_id:
            if self.journal_id.sequence_id and self.journal_id.sequence_id.prefix:
                series = re.sub(r'[^a-zA-Z0-9]', '', self.journal_id.sequence_id.prefix)
            else:
                raise UserError(_("The selected series is not configured"))
            
        self.query_numbering(series)
        document_number = self.get_last_document_number(document_type, series)
        document_number = document_number + 1
        current_number = self.sequence_number

        if document_number != current_number and self.company_id.sequence_validation_tfhka:
            raise UserError(_("The document sequence in Odoo (%s) does not match the sequence in The Factory (%s).Please check your numbering settings.") % (current_number, document_number))

        document_number = str(document_number)

        self.generate_document_data(document_number, document_type, series)

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

    def generate_document_data(self, document_number, document_type, series):
        document_identification = self.get_document_identification(document_type, document_number, series)
        seller = self.get_seller()
        buyer = self.get_buyer()
        totals, foreign_totals = self.get_totals()
        details_items = self.get_item_details()
        additional_information = self.get_additional_information()
        
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
        if additional_information:
            payload["documentoElectronico"]["infoAdicional"] = additional_information
        response = self.call_tfhka_api("emision", payload)

        if response:
            self.is_digitalized = True
            emission_date = fields.Datetime.now().strftime("%d/%m/%Y")
            self.message_post(
                body=_("Document successfully digitized on %(date)s") % {'date': emission_date},  
                message_type='comment',
            )
            num_control_tfhka = response.get("resultado").get("numeroControl")
            self.correlative = num_control_tfhka
            return

    def get_last_document_number(self, document_type, series):
        payload = {
                    "serie": series,
                    "tipoDocumento": document_type,
                }
        response = self.call_tfhka_api("ultimo_documento", payload)
        
        if response == 0:
            return response
        else:
            document_number = response["numeroDocumento"] if response["numeroDocumento"] else response
            return document_number

    def query_numbering(self, series):
        payload={
                "serie": series,
                "tipoDocumento": "",
                "prefix": ""
            }
        response = self.call_tfhka_api("consulta_numeraciones", payload)

        if response:
            approves = False
            for numbering in response.get("numeraciones", []):
                end_number = 0
                start_number = 0
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

    def get_document_identification(self, document_type, document_number, series):
        for record in self:
            now = fields.Datetime.now()
            user_tz = timezone(record.env.user.tz)
            emission_time = now.astimezone(user_tz).strftime("%I:%M:%S %p").lower()
            emission_date = now.astimezone(user_tz).date()
            due_date_obj = record.invoice_date_due

            if due_date_obj:
                if due_date_obj >= emission_date:
                    due_date = due_date_obj.strftime("%d/%m/%Y")
                else:
                    raise ValidationError(_("The expiration date cannot be less than the digitization date."))
            else:
                due_date = emission_date.strftime("%d/%m/%Y")
            
            emission_date = emission_date.strftime("%d/%m/%Y")
            affected_invoice_number = ""
            affected_invoice_date = ""
            affected_invoice_amount = ""
            affected_invoice_comment = ""
            subsidiary = ""
            affected_invoice_series = ""

            if record.debit_origin_id:
                affected_invoice_number = str(record.debit_origin_id.sequence_number)

                affected_invoice_date = record.debit_origin_id.invoice_date.strftime("%d/%m/%Y") if record.debit_origin_id.invoice_date else ""

                if record.debit_origin_id.journal_id.series_correlative_sequence_id:
                    affected_invoice_series = record.debit_origin_id.journal_id.sequence_id.prefix if record.debit_origin_id.journal_id.sequence_id.prefix else ""

                if record.company_id.currency_id.name == "VEF":
                    affected_invoice_amount = str(record.debit_origin_id.amount_total)
                else:
                    tax_totals = record.debit_origin_id.tax_totals
                    affected_invoice_amount = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                part = record.ref.split(',')
                affected_invoice_comment = part[1].strip()

            if record.reversed_entry_id:
                affected_invoice_number = str(record.reversed_entry_id.sequence_number)
                
                affected_invoice_date = record.reversed_entry_id.invoice_date.strftime("%d/%m/%Y") if record.reversed_entry_id.invoice_date else ""

                if record.reversed_entry_id.journal_id.series_correlative_sequence_id:
                    affected_invoice_series = record.reversed_entry_id.journal_id.sequence_id.prefix if record.reversed_entry_id.journal_id.sequence_id.prefix else ""

                if record.company_id.currency_id.name == "VEF":
                    affected_invoice_amount = str(record.reversed_entry_id.amount_total)
                else:
                    tax_totals = record.reversed_entry_id.tax_totals
                    affected_invoice_amount = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                part = record.ref.split(',')
                affected_invoice_comment = part[1].strip()

            if self.company_id.subsidiary:
                if record.account_analytic_id and record.account_analytic_id.code:
                    subsidiary = record.account_analytic_id.code
                else:
                    raise UserError(_("The selected subsidiary does not contain a reference"))

            if not record.invoice_date:
                raise UserError(_("The invoice date is not defined."))

            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "numeroPlanillaImportacion": "",
                "numeroExpedienteImportacion": "",
                "serieFacturaAfectada": affected_invoice_series,
                "numeroFacturaAfectada": affected_invoice_number,
                "fechaFacturaAfectada": affected_invoice_date,
                "montoFacturaAfectada": affected_invoice_amount,
                "comentarioFacturaAfectada": affected_invoice_comment,
                "regimenEspTributacion": "",
                "fechaEmision": emission_date,
                "fechaVencimiento": due_date,
                "horaEmision": emission_time,
                "tipoDePago": self.get_payment_type(),
                "serie": series,
                "sucursal": subsidiary,
                "tipoDeVenta": "Interna",
                "moneda": "VEF",
                "transaccionId": "",
                "urlPdf": ""
            }

    def get_totals(self):
        for record in self:
            currency = record.company_id.currency_id.name
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
                            if group.get('tax_group_name') in ("Exento", "IVA 0%")), 0
                        ), 2
                    )
                )
                amounts["montoExentoTotal"] = str(
                    round(
                        next((
                            group.get('tax_group_base_amount', 0) 
                            for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') in ("Exento", "IVA 0%")
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
                            if group.get('tax_group_name') in ("Exento", "IVA 0%")), 0
                        ), 2
                    )
                )
                amounts_foreign["montoExentoTotal"] = str(
                    round(
                        next((
                            group.get('tax_group_base_amount', 0) 
                            for group in tax_totals.get('groups_by_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') in ("Exento", "IVA 0%")
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
                            if group.get('tax_group_name') in ("Exento", "IVA 0%")), 0
                        ), 2
                    )
                )
                amounts["montoExentoTotal"] = str(
                    round(
                        next((
                            group.get('tax_group_base_amount', 0) 
                            for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])
                            if group.get('tax_group_name') in ("Exento", "IVA 0%")
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
                    "moneda": record.company_id.currency_foreign_id.name,
                    "tipoCambio": str(round(record.foreign_rate, 2)),
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
            "IVA 0%": "E",
        }
        tax_rate = {
            "IVA 8%": "8.0",
            "IVA 16%": "16.0",
            "IVA 31%": "31.0",
            "Exento": "0.0",
            "IVA 0%": "0.0",
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

                if record.company_id.currency_id.name == "VEF":
                    unit_price = round(line.price_unit, 2)
                    unit_price_discount = round(line.price_unit * (line.discount / 10), 2)
                    discount_amount = round((line.price_unit * (line.discount / 100)) * line.quantity, 2)
                    item_price = round(line.price_subtotal, 2)
                    price_before_discount = round(line.price_unit * line.quantity, 2)

                else:
                        unit_price = round(line.foreign_price, 2)
                        unit_price_discount = round(line.foreign_price * (line.discount / 10), 2)
                        discount_amount = round((line.foreign_price * (line.discount / 100)) * line.quantity, 2)
                        item_price = round(line.foreign_subtotal, 2)
                        price_before_discount = round(line.foreign_price * line.quantity, 2)

                vat = round(item_price * line.tax_ids.amount / 100, 2)
                total_item_value = round(item_price + vat, 2)

                item_details.append({
                    "numeroLinea": str(line_number),
                    "codigoPLU": line.product_id.barcode or line.product_id.default_code or "",
                    "indicadorBienoServicio": "2" if line.product_id.type == 'service' else "1",
                    "descripcion": line.product_id.name,
                    "cantidad": str(line.quantity),
                    "precioUnitario": str(unit_price),
                    "precioUnitarioDescuento": str(unit_price_discount),
                    "descuentoMonto": str(discount_amount),
                    "precioItem": str(item_price),
                    "precioAntesDescuento": str(price_before_discount),
                    "codigoImpuesto": tax_mapping[tax_rate],
                    "tasaIVA": str(round(line.tax_ids.amount, 2)),
                    "valorIVA": str(vat),
                    "valorTotalItem": str(total_item_value),
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

    def get_additional_information(self):
        additional_information = []
        for record in self:
            if record.guide_number:
                additional_information.append({
                    "campo": "numeroGuia",
                    "valor": str(record.guide_number),
                })

        return additional_information
    
    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'is_digitalized')
    def _compute_invisible_check(self):
        for record in self:
            self.show_digital_invoice = True
            if record.is_digitalized:
                continue
            if record.state != "posted":
                continue
            if record.debit_origin_id or record.reversed_entry_id:
                continue
            if record.move_type != "out_invoice":
                continue
            if not self.company_id.invoice_digital_tfhka:
                continue
            record.show_digital_invoice = False
