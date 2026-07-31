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

    is_digitalized = fields.Boolean(default=False, copy=False, tracking=True)
    show_digital_invoice = fields.Boolean(compute="_compute_invisible_check", copy=False)
    show_digital_debit_note = fields.Boolean(string="Show Digital Note Debit", compute="_compute_invisible_check", copy=False)
    show_digital_credit_note = fields.Boolean(string="Show Digital Note Credit", compute="_compute_invisible_check", copy=False)

    def action_post(self):
        for invoice in self:
            invoice._tfhka_validate_mixed_invoicing()

        res = super(AccountMove, self).action_post()
        return res

    def _is_eligible_for_tfhka(self):
        """Check if the invoice should process TFHKA logic."""
        self.ensure_one()
        config_invoice_can_be_digitalized = self.company_id.invoice_digital_tfhka
        if not self.journal_id.digital_invoice or not config_invoice_can_be_digitalized:
            return False
        if self.move_type not in ("out_invoice", "out_refund"):
            return False
        return True

    def _tfhka_validate_mixed_invoicing(self):
        """Validates if mixed invoicing is allowed."""
        self.ensure_one()
        config_invoice_can_be_digitalized = self.company_id.invoice_digital_tfhka
        config_mix_invoicing = self.company_id.mix_invoicing_tfhka

        if not self.journal_id.digital_invoice and config_invoice_can_be_digitalized and not config_mix_invoicing:
            if self.move_type in ['out_invoice', 'out_refund']:
                raise ValidationError(_(
                    "The company is configured for strict digital invoicing (mixed invoicing is disabled). "
                    "Only journals with digital invoicing enabled are allowed for this operation. "
                    "Please check the company configuration or select a valid digital journal."
                ))

    def _tfhka_get_document_type_and_series(self):
        """Returns the TFHKA document type and series."""
        self.ensure_one()
        document_type = ""
        if self.move_type == "out_invoice":
            document_type = "03" if self.debit_origin_id else "01"
        elif self.move_type == "out_refund" and self.reversed_entry_id:
            document_type = "02"
        
        series = ""
        if self.company_id.group_sales_invoicing_series and self.journal_id.series_correlative_sequence_id:
            if self.journal_id.sequence_id and self.journal_id.sequence_id.prefix:
                series = re.sub(r'[^a-zA-Z0-9]', '', self.journal_id.sequence_id.prefix)
            else:
                raise UserError(_("The selected series is not configured"))
                
        return document_type, series

    # --- MULTI-MONEDA ---
    # Flag por factura: habilita el selector de moneda de línea (VES/USD).
    # Requiere que multi_currency_invoice_tfhka esté activo en la compañía.
    multi_currency_invoice = fields.Boolean(
        string='Multi-Currency Invoice',
        default=False,
        tracking=True,
        help="When enabled, the 'Line Currency' selector appears, allowing you to "
             "choose VES (prices in Bolivars, totals in VES) or USD (prices in USD, "
             "totals in both currencies). "
             "Requires 'Multi-currency digital invoicing' in company settings."
    )
    # Indica si la funcionalidad multi-moneda está disponible (según compañía).
    # Controla la visibilidad del campo multi_currency_invoice en vista.
    multi_currency_enabled = fields.Boolean(
        string='Multi-currency enabled',
        compute='_compute_multi_currency_enabled',
        store=False
    )

    @api.depends('company_id.multi_currency_invoice_tfhka')
    def _compute_multi_currency_enabled(self):
        for move in self:
            move.multi_currency_enabled = move.company_id.multi_currency_invoice_tfhka

    # Moneda de las líneas de producto: VES (precios en Bs.) o USD (precios en USD).
    # Solo visible cuando multi_currency_invoice está activo en la factura.
    line_currency = fields.Selection([
        ('VES', 'VES'),
        ('USD', 'USD'),
    ], default='VES',
       help="VES: precios de líneas en Bolívares, totales solo en VES.\n"
            "USD: precios de líneas en dólares, totales en ambas monedas.")

    # Resuelve si esta factura debe tratarse como multi-moneda.
    # El modo multi-moneda (USD + totales bimoneda) se activa solo cuando
    # multi_currency_invoice=True y line_currency='USD'.
    # Sigue el patrón de binaural_unidigital con la adición de line_currency.
    def is_invoice_multi_currency_enabled(self):
        self.ensure_one()
        return bool(self.multi_currency_invoice and self.line_currency == 'USD')

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
            raise UserError(_("The document sequence in Odoo (%(odoo_seq)s) does not match the sequence in The Factory (%(factory_seq)s).Please check your numbering settings.", odoo_seq=current_number, factory_seq=document_number))

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
            raise UserError(_("Endpoint '%(endpoint_key)s' is not defined.", endpoint_key=endpoint_key))

        url = f"{base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.get_token()}"}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
        
            if response.status_code == 200:
                data = response.json()
                if data.get("codigo") == "200":
                    return data
                elif data.get("codigo") == "203" and data.get("validaciones") and endpoint_key == "ultimo_documento":
                    return 0
                else:
                    _logger.error("Error in the API response: %s \n%s", data.get('mensaje'), data.get('validaciones'))
                    raise UserError(_("Error in the API response: %(message)s \n%(validation)s", message=data.get('mensaje'), validation=data.get('validaciones')))
            if response.status_code == 401:
                _logger.error(_("Error 401: Invalid or expired token."))
                self.company_id.generate_token_tfhka()
                return self.call_tfhka_api(endpoint_key, payload)
            else:
                _logger.error("HTTP error %s: %s", response.status_code, response.text)
                raise UserError(_("HTTP error %(status_code)s: %(text)s", status_code=response.status_code, text=response.text))
        except requests.exceptions.RequestException as e:
            _logger.error("Error connecting to the API: %s", e)
            raise UserError(_("Error connecting to the API: %(error)s", error=e))

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
                body=_("Document successfully digitized on %(date)s", date=emission_date),  
                message_type='comment',
            )
            num_control_tfhka = response.get("resultado").get("numeroControl")
            self.correlative = num_control_tfhka
            
            # Autocorrección reactiva de secuencia local posterior a la generación
            if self.company_id.sequence_validation_tfhka:
                nuevo_correlativo_tfhka = int(document_number) + 1
                try:
                    if self.move_type == "out_refund":
                        self.journal_id.sudo().write({"refund_sequence_number_next": nuevo_correlativo_tfhka})
                    else:
                        self.journal_id.sudo().write({"sequence_number_next": nuevo_correlativo_tfhka})
                    _logger.info("Secuencia actualizada localmente a %s basada en la última generación a TFHKA", nuevo_correlativo_tfhka)
                except Exception as e:
                    _logger.error("No se pudo actualizar la secuencia post-generación TFHKA: %s", e)
                    
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

    def query_numbering(self, series=""):
        payload={
                "serie": series,
                "tipoDocumento": "",
                "prefix": ""
            }
        response = self.call_tfhka_api("consulta_numeraciones", payload)

        if response:
            approves = False
            found_series = False
            for numbering in response.get("numeraciones", []):
                serie_tfhka = numbering.get("serie", "")
                if serie_tfhka != series and serie_tfhka != "NO APLICA":
                    continue
                
                end_number = numbering.get("hasta")
                start_number = numbering.get("correlativo")
                found_series = True

                if int(start_number) < int(end_number):
                    approves = True
                    break
                
            if not found_series:
                raise UserError(_("The series '%(series)s' is not configured in The Factory HKA. Please contact the administrator.", series=series))
            
            if not approves:
                raise UserError(_("The numbering range is exhausted. Please contact the administrator."))

            return

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
                    _logger.error(
                        "Fecha vencimiento (%s) anterior a fecha emisión (%s) — invoice=%s",
                        due_date_obj, emission_date, record.id
                    )
                    raise ValidationError(_("The expiration date cannot be less than the digitization date."))
            else:
                due_date = emission_date.strftime("%d/%m/%Y")
            
            emission_date = emission_date.strftime("%d/%m/%Y")
            affected_invoice_number = ""
            affected_invoice_date = ""
            affected_invoice_amount = ""
            affected_invoice_comment = record.ref if record.debit_origin_id or record.reversed_entry_id else ""
            affected_invoice_series = ""

            if record.debit_origin_id:
                affected_invoice_number = str(record.debit_origin_id.sequence_number)

                affected_invoice_date = record.debit_origin_id.invoice_date.strftime("%d/%m/%Y") if record.debit_origin_id.invoice_date else ""

                if record.debit_origin_id.journal_id.series_correlative_sequence_id:
                    affected_invoice_series = record.debit_origin_id.journal_id.sequence_id.prefix if record.debit_origin_id.journal_id.sequence_id.prefix else ""

                if record.company_id.currency_id.name in ('VEF', 'VES'):
                    affected_invoice_amount = str(round(record.debit_origin_id.amount_total, 2))
                else:
                    tax_totals = record.debit_origin_id.tax_totals
                    affected_invoice_amount = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                if record.ref and ',' in record.ref:
                    affected_invoice_comment = record.ref.split(',', 1)[1].strip()

            if record.reversed_entry_id:
                affected_invoice_number = str(record.reversed_entry_id.sequence_number)
                
                affected_invoice_date = record.reversed_entry_id.invoice_date.strftime("%d/%m/%Y") if record.reversed_entry_id.invoice_date else ""

                if record.reversed_entry_id.journal_id.series_correlative_sequence_id:
                    affected_invoice_series = record.reversed_entry_id.journal_id.sequence_id.prefix if record.reversed_entry_id.journal_id.sequence_id.prefix else ""

                if record.company_id.currency_id.name in ('VEF', 'VES'):
                    affected_invoice_amount = str(round(record.reversed_entry_id.amount_total, 2))
                else:
                    tax_totals = record.reversed_entry_id.tax_totals
                    affected_invoice_amount = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                _logger.info(
                    "NC — factura_afectada=%s monto=%s serie=%s date=%s",
                    affected_invoice_number, affected_invoice_amount,
                    affected_invoice_series, affected_invoice_date
                )

                if record.ref and ',' in record.ref:
                    affected_invoice_comment = record.ref.split(',', 1)[1].strip()

            if not record.invoice_date:
                _logger.error("Fecha de emisión no definida — invoice=%s", record.id)
                raise UserError(_("The invoice date is not defined."))

            # Determina la moneda del documento.
            # line_currency='USD' + multi_currency_invoice → Moneda = USD.
            if record.is_invoice_multi_currency_enabled():
                currency_tfhka = 'USD'
                _logger.info("Moneda resuelta: USD (multi_currency activo) — invoice=%s", record.id)
            else:
                currency_tfhka = record.company_id.currency_foreign_id.code_tfhka
                if record.company_id.currency_id.name in ('VEF', 'VES'):
                    currency_tfhka = record.company_id.currency_id.code_tfhka
                _logger.info(
                    "Moneda resuelta: %s (compañía=%s, foreign=%s) — invoice=%s",
                    currency_tfhka,
                    record.company_id.currency_id.name,
                    record.company_id.currency_foreign_id.code_tfhka,
                    record.id
                )

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
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": currency_tfhka,
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
            # Resuelve si esta factura opera en modo multi-moneda.
            # Verifica primero el flag por factura, luego el de compañía.
            multi_currency = record.is_invoice_multi_currency_enabled()

            if currency == "VEF" or currency == "VES":
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

                taxes_subtotal, _dummy = self.get_tax_subtotals(currency)
                currency_tfhka_code = record.company_id.currency_id.code_tfhka

                # TotalesOtraMoneda activo: factura VEF/VES con tipo de cambio.
                # Se genera cuando multi_currency_invoice=True + line_currency='USD'
                # (multi_currency), o cuando hay un foreign_rate (ej. desde POS).
                # Enviamos Totales en VES (amounts) y TotalesOtraMoneda en USD
                # (amounts_foreign = amounts / tasa de cambio).
                has_foreign_rate = bool(record.foreign_rate)
                if multi_currency or has_foreign_rate:
                    rate = record.foreign_rate or 1.0
                    amounts_foreign["montoGravadoTotal"] = str(
                        round(float(amounts["montoGravadoTotal"]) / rate, 2)
                    )
                    amounts_foreign["montoExentoTotal"] = str(
                        round(float(amounts["montoExentoTotal"]) / rate, 2)
                    )
                    amounts_foreign["subtotal"] = str(
                        round(float(amounts["subtotal"]) / rate, 2)
                    )
                    amounts_foreign["subtotalAntesDescuento"] = str(
                        round(float(amounts["subtotalAntesDescuento"]) / rate, 2)
                    )
                    amounts_foreign["totalAPagar"] = str(
                        round(float(amounts["totalAPagar"]) / rate, 2)
                    )
                    amounts_foreign["totalIVA"] = round(
                        float(amounts["totalIVA"]) / rate, 2
                    )
                    amounts_foreign["montoTotalConIVA"] = str(
                        round(float(amounts["montoTotalConIVA"]) / rate, 2)
                    )
                    amounts_foreign["totalDescuento"] = str(
                        abs(round(float(amounts["totalDescuento"]) / rate, 2))
                    )
                    # Impuestos desglosados en ambas monedas para ImpuestosSubtotal.
                    _dummy, taxes_subtotal_foreign = self.get_tax_subtotals(
                        currency, multi_currency=True
                    )
                    # Código de moneda extranjera (ej. "USD") para TotalesOtraMoneda.
                    foreign_currency_code = (
                        record.company_id.currency_foreign_id.code_tfhka
                    )
                else:
                    foreign_currency_code = None

                currency = currency_tfhka_code

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
                currency = record.company_id.currency_foreign_id.code_tfhka
                # Caso moneda extranjera: el código de moneda para TotalesOtraMoneda
                # es el mismo que currency_foreign_id (viene del else branch).
                foreign_currency_code = currency

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
                if len(payment_forms) > 5:
                    raise UserError(_("The maximum number of payment methods is 5. Please check your payment methods."))
                if any(not method.get('forma') for method in payment_forms):
                    raise ValidationError(_("The payment method code is not configured in the journal."))
                totals["formasPago"] = payment_forms

            if amounts_foreign:
                # foreign_currency_code se setea en multi-moneda (VEF+USD) o en
                # moneda extranjera (USD). Fallback a currency por si acaso.
                foreign_totals = {
                    "moneda": foreign_currency_code or currency,
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

    # multi_currency=True: factura VEF/VES con flag multi-moneda activo.
    # Retorna (tax_subtotals_VES, tax_subtotals_USD) donde los montos USD
    # se obtienen dividiendo los montos VES por la tasa de cambio.
    def get_tax_subtotals(self, currency, multi_currency=False):
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
            if currency == "VEF" and not multi_currency:
                for tax_totals in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    tax_subtotals.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    })
                return tax_subtotals, tax_subtotals_foreign
            # Rama multi-moneda: factura en VES con flag multi_currency activo.
            # Se construyen dos listas de impuestos:
            #   - tax_subtotals: montos en VES (base imponible original).
            #   - tax_subtotals_foreign: montos convertidos a USD ÷ tasa de cambio.
            elif multi_currency:
                rate = record.foreign_rate or 1.0
                for tax_line in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    tax_subtotals.append({
                        "codigoTotalImp": tax_code[tax_line.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_line.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_line.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_line.get('tax_group_amount'), 2)),
                    })
                if record.tax_totals.get('igtf', {}).get('apply_igtf'):
                    igtf = record.tax_totals.get('igtf', {})
                    tax_subtotals.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax_rate.get(igtf.get('name'), "3.0"),
                        "baseImponibleImp": str(round(igtf.get('igtf_base_amount'), 2)),
                        "valorTotalImp": str(round(igtf.get('igtf_amount'), 2)),
                    })
                for tax_line in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    tax_subtotals_foreign.append({
                        "codigoTotalImp": tax_code[tax_line.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_line.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_line.get('tax_group_base_amount') / rate, 2)),
                        "valorTotalImp": str(round(tax_line.get('tax_group_amount') / rate, 2)),
                    })
                if record.tax_totals.get('igtf', {}).get('apply_igtf'):
                    igtf = record.tax_totals.get('igtf', {})
                    tax_subtotals_foreign.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax_rate.get(igtf.get('name'), "3.0"),
                        "baseImponibleImp": str(round(igtf.get('igtf_base_amount') / rate, 2)),
                        "valorTotalImp": str(round(igtf.get('igtf_amount') / rate, 2)),
                    })
                return tax_subtotals, tax_subtotals_foreign
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
            product_lines = record.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product'
            )
            for line in product_lines:
                tax_mapping = {
                    0.0: "E",
                    8.0: "R",
                    16.0: "G",
                    31.0: "A",
                }
                taxes = line.tax_ids.filtered(lambda t: t.amount)
                tax_rate = taxes[0].amount if taxes else 0.0

                # Rama USD multi-moneda: convierte precios VES → USD vía foreign_rate.
                if record.is_invoice_multi_currency_enabled():
                    rate = record.foreign_rate or 1.0
                    unit_price = round(line.price_unit / rate, 2)
                    unit_price_discount = round((line.price_unit / rate) * (line.discount / 10), 2)
                    discount_amount = round(((line.price_unit / rate) * (line.discount / 100)) * line.quantity, 2)
                    item_price = round(line.price_subtotal / rate, 2)
                    price_before_discount = round((line.price_unit / rate) * line.quantity, 2)

                elif record.company_id.currency_id.name == "VEF":
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
                    "descripcion": line.product_id.name or "",
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
                content_data = record.invoice_payments_widget.get("content", []) if record.invoice_payments_widget else []
                if content_data:
                    for item in content_data:
                        payment = self.get_payment(item.get('account_payment_id'))

                        if not payment:
                            continue
                        
                        payment_info = self.build_payment_info(payment)
                        payment_data.append(payment_info)
                    return payment_data
            return False
        except Exception as e:
            _logger.error("Error processing payment methods: %s", e)
            return False

    def get_currency(self, currency_id):
        currency_data = self.env['res.currency'].search([('id', '=', currency_id)])
        return currency_data.name if currency_data else ""

    def get_payment(self, account_payment_id):
        return self.env['account.payment'].search([('id', '=', account_payment_id)])

    # Construye la info de forma de pago para el payload HKA.
    # Con multi-moneda activo: pagos en VES se reportan como "VES" sin tipo de cambio.
    # Pagos en USD se reportan con su moneda y tipoCambio explícito.
    def build_payment_info(self, payment):
        payment_id = self.env['account.payment'].search([('id', '=', payment.id)])
        payment_currency = payment_id.currency_id.name if payment_id.currency_id else "VES"
        payment_method = payment_id.journal_id.payment_method_code if payment_id.journal_id.payment_method_code else False
        multi_currency = self.is_invoice_multi_currency_enabled()

        if payment_currency == "VEF" or payment_currency == "VES":
            if multi_currency:
                # Multi-moneda: el pago en VES se reporta como moneda local VES.
                currency_code = self.company_id.currency_id.code_tfhka
                tipo_cambio = None
            else:
                # Sin multi-moneda: se usa el código TFHKA de la moneda local.
                currency_code = self.company_id.currency_foreign_id.code_tfhka
                if self.company_id.currency_id.name in ('VEF', 'VES'):
                    currency_code = self.company_id.currency_id.code_tfhka
                tipo_cambio = None
        else:
            # Pago en moneda extranjera (USD, EUR, etc.): se incluye tipo de cambio.
            currency_code = payment_currency
            tipo_cambio = str(round(payment_id.foreign_rate, 2))

        payment_info = {
            "descripcion": payment_method.description if payment_method else "",
            "fecha": payment_id.date.strftime("%d/%m/%Y") if payment_id.date else "",
            "forma": payment_method.code if payment_method else "",
            "monto": str(round(payment_id.amount, 2)),
            "moneda": currency_code,
        }

        if tipo_cambio:
            payment_info["tipoCambio"] = tipo_cambio

        return payment_info

    def get_additional_information(self):
        additional_information = []
        # for record in self:
        #     if record.guide_number:
        #         additional_information.append({
        #             "campo": "numeroGuia",
        #             "valor": str(record.guide_number),
        #         })

        return additional_information
    
    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'is_digitalized')
    def _compute_invisible_check(self):
        for record in self:
            record.show_digital_invoice = True
            record.show_digital_debit_note = True
            record.show_digital_credit_note = True

            if record.state != "posted" or record.is_digitalized or not self.company_id.invoice_digital_tfhka or not record.journal_id.digital_invoice:
                continue

            if (
                record.reversed_entry_id
                and record.reversed_entry_id.is_digitalized
            ):
                record.show_digital_credit_note = False

            elif (
                record.debit_origin_id
                and record.debit_origin_id.is_digitalized
            ):
                record.show_digital_debit_note = False

            elif (
                record.move_type == "out_invoice"
                and not record.debit_origin_id
            ):
                record.show_digital_invoice = False
