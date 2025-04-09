from odoo import models, api, fields
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from cachetools import TTLCache
import json

cache = TTLCache(maxsize=1, ttl=43200)
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    
    _inherit = 'account.move'
    
    document_digital_check_tfhka = fields.Boolean(string="Digitalizado", default=False, readonly=True, copy=False)
    show_digital_invoice = fields.Boolean(string="Show Digital Invoice", compute="_compute_invisible_check", copy=False)
    show_digital_note_debit= fields.Boolean(string="Show Digital Note Debit", compute="_compute_invisible_check", copy=False)
    show_digital_note_credit = fields.Boolean(string="Show Digital Note Credit", compute="_compute_invisible_check", copy=False)
    
    def action_post(self):
        for record in self:
            if record.name == '/':
                last_invoice = self.env['account.move'].search(
                    [
                        ('move_type', '!=', 'entry'),
                        ('name', '!=', '/')
                    ], order='create_date desc', limit=1
                )
                if not last_invoice.name:
                    super().action_post()
                elif not last_invoice.document_digital_check_tfhka:
                    selection_dict = dict(last_invoice._fields['move_type'].selection)
                    move_type_name = selection_dict.get(last_invoice.move_type)
                    raise ValidationError(f"La {move_type_name} {last_invoice.name} aún no ha sido digitalizada.\n"
                                            "Por favor, realice la digitalización antes de continuar con el proceso.")
                else:
                    super().action_post()
            else:
                super().action_post()

    def Emission(self):
        if self.document_digital_check_tfhka:
            raise UserError("El documento ya ha sido digitalizado.")
        tipoDocumento = self.env.context.get('tipoDocumento')
        url,token = self.GenerateToken()
        hasta, inicio = self.ConsultaNumeracion(url, token)
        numeroDocumento = self.UltimoDocumento(url, token, tipoDocumento)
        numeroDocumento = str(numeroDocumento + 1)
        
        if numeroDocumento is inicio:
            self.AsignarNumeracion(self, url, token, hasta, inicio)
        _logger.info(f"Se esta ejecturando emision")
        
        data = self.GenerateDocument(numeroDocumento, tipoDocumento)
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url + "/Emision", json=data, headers=headers)
        respuesta_json = response.json()
        codigo = respuesta_json.get("codigo")
        mensaje = respuesta_json.get("mensaje")
        validaciones = respuesta_json.get("validaciones")
        if response.status_code is 200:
            if codigo == "200":
                _logger.info("Documento emitido correctamente")
                success_message = {
                    "01": "Factura Digital generada exitosamente",
                    "02": "Nota Crédito Digital generada exitosamente",
                    "03": "Nota Débito Digital generada exitosamente"
                }
                self.document_digital_check_tfhka = True
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Generado exitosamente',
                        'message': f'{success_message[tipoDocumento]}',
                        'type': 'success',
                        'sticky': False,
                        'next': {'type': 'ir.actions.client', 'tag': 'reload'}
                    }
                }
            
            else:
                _logger.error(f"Error al emitir documento: {mensaje}")
                raise UserError(f"Error al emitir documento: {mensaje}")
        else:
            _logger.error(f"Error {response.status_code}, {mensaje}")
            raise UserError(f"Error {response.status_code}: {validaciones}")

    def GenerateDocument(self, numeroDocumento, tipoDocumento):
        for record in self:
            hora = record.create_date.strftime("%I:%M:%S %p").lower()
            numeroFacturaAfectada = ""
            fecha_emision_afectada = ""
            montoFacturaAfectada = ""
            comentarioFacturaAfectada = ""

            if record.debit_origin_id:
                numeroFacturaAfectada = record.debit_origin_id.name
                fecha_emision_afectada = record.debit_origin_id.invoice_date.strftime("%d/%m/%Y") if record.debit_origin_id.invoice_date else ""
                
                if record.currency_id.name == "VEF":
                    montoFacturaAfectada = str(record.debit_origin_id.amount_total)
                elif record.currency_id.name == "USD":
                    tax_totals = record.debit_origin_id.tax_totals
                    montoFacturaAfectada = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                part = record.display_name.split(',')
                comentarioFacturaAfectada = part[1].strip().rstrip(')')
                
            if record.reversed_entry_id:
                numeroFacturaAfectada = record.reversed_entry_id.name
                fecha_emision_afectada = record.reversed_entry_id.invoice_date.strftime("%d/%m/%Y") if record.reversed_entry_id.invoice_date else ""
                
                if record.currency_id.name == "VEF":
                    montoFacturaAfectada = str(record.reversed_entry_id.amount_total)
                elif record.currency_id.name == "USD":
                    tax_totals = record.reversed_entry_id.tax_totals
                    montoFacturaAfectada = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))

                part = record.display_name.split(',')
                comentarioFacturaAfectada = part[1].strip().rstrip(')')

            fecha_emision = record.invoice_date.strftime("%d/%m/%Y") if record.invoice_date else ""
            fecha_vencimiento = record.invoice_date_due.strftime("%d/%m/%Y") if record.invoice_date_due else ""
            identificacionDocumento = {
                "tipoDocumento": tipoDocumento,
                "numeroDocumento": numeroDocumento,
                "numeroPlanillaImportacion": "",
                "numeroExpedienteImportacion": "",
                "serieFacturaAfectada": "",
                "numeroFacturaAfectada": numeroFacturaAfectada,
                "fechaFacturaAfectada": fecha_emision_afectada,
                "montoFacturaAfectada": montoFacturaAfectada,
                "comentarioFacturaAfectada": comentarioFacturaAfectada,
                "regimenEspTributacion": "",
                "fechaEmision": fecha_emision,
                "fechaVencimiento": fecha_vencimiento,
                "horaEmision": hora,
                # "anulado": False,
                "tipoDePago": self.GetPaymentType(),
                "serie": "",
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": record.currency_id.name,
                "transaccionId": "",
                "urlPdf": ""
            }
            if "seller_id" in record._fields and record.seller_id:
                vendedor = {
                    "codigo": str(record.seller_id.id),
                    "nombre": record.seller_id.name,
                    "numCajero": ""
                }
            comprador = self.GetPartner()
            totales, totalesOtraMoneda = self.GetTotales()
            detallesItems = self.GetDetallesItems()
        data = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": identificacionDocumento,
                    "comprador": comprador,
                    "totales": totales,
                },
                "detallesItems": detallesItems,
            }
        }
        if "seller_id" in record._fields:
            data["documentoElectronico"]["encabezado"]["vendedor"] = vendedor

        if totalesOtraMoneda:
            data["documentoElectronico"]["encabezado"]["totalesOtraMoneda"] = totalesOtraMoneda

        return data

    def UltimoDocumento(self, url, token, tipoDocumento):
        _logger.info(f"Se esta ejecutando ultimodocumento")

        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.post(url + "/UltimoDocumento", json={
                "serie": "",
                "tipoDocumento": tipoDocumento,
            }, headers=headers)
        response_json = response.json()
        codigo = response_json.get("codigo")
        mensaje = response_json.get("mensaje")
        
        if response.status_code == 200:
            if codigo == "200":
                numeroDocumento = response_json["numeroDocumento"]
                return numeroDocumento
            else:
                _logger.error(f"Error {codigo}, {mensaje}")
                raise UserError(f"Error {codigo}: {mensaje}")
        else:
            _logger.error(f"Error {response.status_code}, {mensaje}")
            raise UserError(f"Error {response.status_code}: {mensaje}")

    def AsignarNumeracion(self, url, token, hasta, inicio):
        fin = inicio + 20
        inicio += 1
        
        _logger.info(f"Se esta ejecutando asignar numeracion")
        if inicio <= hasta:
            headers = {
                "Authorization": f"Bearer {token}"
            }
            response = requests.post(url + "/AsignarNumeraciones", json={
                "serie": "",
                "tipoDocumento": "01",
                "numeroDocumentoInicio": inicio,
                "numeroDocumentoFin": fin
            }, headers=headers)
            response_json = response.json()
            codigo = response_json.get("codigo")
            mensaje = response_json.get("mensaje")
            
            if response.status_code == 200:
                if codigo == "200":
                    _logger.info("Rango de numeración asignado correctamente.")
                else:
                    _logger.warning(f"Error {codigo}, {mensaje}")
                    raise UserError(f"Error {codigo}: {mensaje}")
            else:
                _logger.error(f"Error: {response.status_code}, {mensaje}")
                raise UserError(f"Error: {response.status_code}: {mensaje}")
        else:
            _logger.error("El rango de numeración asignado ha sido superado.")
            raise UserError("El rango de numeración asignado ha sido superado.")

    def ConsultaNumeracion(self, url, token):
        _logger.info(f"Se esta ejecutando consulta numeracion")

        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.post(url + "/ConsultaNumeraciones", json={
                "serie": "",
                "tipoDocumento": "",
                "prefix": ""
            }, headers=headers)
        respuesta_json = response.json()
        codigo = respuesta_json.get("codigo")
        mensaje = respuesta_json.get("mensaje")
        
        if response.status_code == 200:
            if codigo == "200":
                numeracion = respuesta_json["numeraciones"][0]
                hasta = numeracion.get("hasta")
                inicio = numeracion.get("correlativo")
                return hasta, inicio
            else:
                _logger.error(f"Error {codigo}, {mensaje}")
                raise UserError(f"Error {codigo}: {mensaje}")
        else:
            _logger.error(f"Error: {response.status_code}, {mensaje}")
            raise UserError(f"Error: {response.status_code}: {mensaje}")

    def GenerateToken(self):           
        username, password, url = self.ObtenerCredencial()
        
        if "auth_token" not in cache:
            _logger.info(f"Se esta ejecutando Generar Token")
            respuesta = requests.post(url + "/Autenticacion", json={
                "usuario": username,
                "clave": password
            })
            respuesta_json = respuesta.json()
            codigo = respuesta_json.get("codigo")
            mensaje = respuesta_json.get("mensaje")
            
            if respuesta.status_code == 200:
                if codigo == 200 and "token" in respuesta_json:
                    token = respuesta_json["token"]
                    cache["auth_token"] = token
                    return url, token
                elif codigo == 403:
                    raise ValidationError(f"Configuración del Módulo incorrecta: {mensaje}")
                else:
                    _logger.error(f"Error: {codigo}, {mensaje}")
                    raise UserError(f"Error: {codigo} \n{mensaje}")
            else: 
                _logger.error(f"Error: {respuesta.status_code}", {mensaje})
                raise UserError(f"Error {respuesta.status_code}: {mensaje}")
        else:
            _logger.info("El token aún es válido.")
            token = cache["auth_token"]
            return url, token

    def ObtenerCredencial(self):
        
        username = None
        password = None
        url = None
        
        for move in self:
            if move.company_id.username_tfhka and move.company_id.password_tfhka and move.company_id.url_tfhka:
                username = move.company_id.username_tfhka
                password = move.company_id.password_tfhka
                url = move.company_id.url_tfhka
                return username, password, url
            else:
                _logger.error("USERNAME, PASSWORD o URL vacío.")
                raise ValidationError("Configuración del Módulo incorrecta: USERNAME, PASSWORD o URL vacío.")
    
    def GetTotales(self):
        _logger.info(f"Se esta ejecutando Totales")

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
                
                impuestosSubtotal = self.GetImpuestosSubtotal(currency)

            elif currency == "USD":
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
                
                impuestosSubtotal, impuestosSubtotal_foreign = self.GetImpuestosSubtotal(currency)
            totales = {
                "nroItems": str(len(record.invoice_line_ids)),
                "montoGravadoTotal": amounts["montoGravadoTotal"],
                "montoExentoTotal": amounts["montoExentoTotal"],
                "subtotal": amounts["subtotal"],
                "subtotalAntesDescuento": amounts["subtotalAntesDescuento"],
                "totalAPagar": amounts["totalAPagar"],
                "totalIVA": str(amounts["totalIVA"]),
                "montoTotalConIVA": amounts["montoTotalConIVA"],
                "totalDescuento": amounts["totalDescuento"],
                "impuestosSubtotal": impuestosSubtotal,
                "totalIGTF": str(totalIGTF),
                "totalIGTF_VES": str(totalIGTF_VES),
            }
            formasPago = self.GetPaymentMethod()

            if formasPago:
                totales["formasPago"] = formasPago

            if amounts_foreign:
                totalesOtraMoneda = {
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
                    "impuestosSubtotal": impuestosSubtotal_foreign,
                }
            else:
                totalesOtraMoneda = False
        return totales, totalesOtraMoneda
    
    def GetImpuestosSubtotal(self, currency):
        _logger.info(f"Se esta ejecutando impuestos subtotal")
        impuestosSubtotal = []
        impuestosSubtotal_foreign = []
        tax_code = {
            "IVA 8%": "R",
            "IVA 16%": "G",
            "IVA 31%": "A",
            "Exento": "E",
        }
        tax = {
            "IVA 8%": "8.0",
            "IVA 16%": "16.0",
            "IVA 31%": "31.0",
            "Exento": "0.0",
            "3.0 %": "3.0"
        }
        for record in self:
            if currency == "VEF":
                for tax_totals in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    impuestosSubtotal.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    },)
                return impuestosSubtotal
            else:
                for tax_totals in record.tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', []):
                    impuestosSubtotal.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    },)
                for tax_totals in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    impuestosSubtotal_foreign.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    },)
                if record.tax_totals.get('igtf', {}).get('apply_igtf'):
                    igtf = record.tax_totals.get('igtf', {})
                    impuestosSubtotal_foreign.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax[igtf.get('name')],
                        "baseImponibleImp": str(round(igtf.get('igtf_base_amount'), 2)),
                        "valorTotalImp": str(round(igtf.get('igtf_amount'), 2)),
                    },)
                    impuestosSubtotal.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax[igtf.get('name')],
                        "baseImponibleImp": str(round(igtf.get('foreign_igtf_base_amount'), 2)),
                        "valorTotalImp": str(round(igtf.get('foreign_igtf_amount'), 2)),
                    },)
                return impuestosSubtotal, impuestosSubtotal_foreign

    def GetDetallesItems(self):
        detallesItems = []
        contador = 1
        for record in self:
            for line in record.invoice_line_ids:
                impuesto = {
                    8.0: "R",
                    16.0: "G",
                    31.0: "A",
                    0.0: "E",
                    }
                detallesItems.append({
                    "numeroLinea": str(contador),
                    "codigoPLU": line.product_id.barcode or line.product_id.default_code or "",
                    "indicadorBienoServicio": "2" if line.product_id.type == 'service' else "1",
                    "descripcion": line.product_id.name,
                    "cantidad": str(line.quantity),
                    "precioUnitario": str(round(line.price_unit, 2)),
                    "precioUnitarioDescuento": str(round(line.price_unit * (line.discount / 100), 2)),
                    "descuentoMonto": str(round((line.price_unit * (line.discount / 100)) * line.quantity, 2)),
                    "precioItem": str(round(line.price_subtotal, 2)),
                    "precioAntesDescuento": str(round(line.price_unit * line.quantity, 2)),
                    "codigoImpuesto": impuesto[line.tax_ids.amount],
                    "tasaIVA": str(round(line.tax_ids.amount, 2)),
                    "valorIVA": str(round(line.price_total - line.price_subtotal, 2)),
                    "valorTotalItem": str(round(line.price_subtotal, 2)),
                })
                contador += 1
        return detallesItems
    
    def GetPartner(self):
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
                    raise UserError("El campo 'País' del Cliente no puede estar vacío para digitalizar.")

                if not (record.partner_id.mobile or record.partner_id.phone):
                    raise UserError("El campo 'Móvil' del Cliente no puede estar vacío para digitalizar.")

                if not record.partner_id.email:
                    raise UserError("El campo 'Correo' del Cliente no puede estar vacío para digitalizar.")

                comprador = {
                    "tipoIdentificacion": partner_data["tipoIdentificacion"],
                    "numeroIdentificacion": partner_data["numeroIdentificacion"],
                    "razonSocial": partner_data["razonSocial"],
                    "direccion": partner_data["direccion"],
                    "pais": partner_data["pais"],
                    "telefono": [partner_data["telefono"]],
                    "notificar": "Si",
                    "correo": [partner_data["correo"]],
                }
            return comprador
        return None
    
    def GetPaymentType(self):
        for record in self:
            if not record.invoice_payment_term_id:
                return "Inmediato"
            elif record.invoice_payment_term_id and record.invoice_payment_term_id.name == "Pago inmediato":
                return "Inmediato"
            else:
                return "crédito"

    def GetPaymentMethod(self):
        try:
            for record in self:
                content_data = record.invoice_payments_widget.get("content", [])
                if content_data:
                    payment_data = []

                    for item in content_data:
                        payment = self.env['account.payment'].search(
                            [
                                ('id', '=', item.get('account_payment_id', 0)),
                            ]
                        )
                        currency = payment.currency_id.name

                        if item.get("payment_method_name") == "Efectivo":
                            if currency == "VES":
                                payment_method = "08"
                            else:
                                payment_method = "09"
                        elif item.get("payment_method_name") == "Transferencia":
                            payment_method = "03"

                        if currency == "VES" and payment:
                            payment_data.append({
                                "descripcion": payment.concept ,
                                "fecha": item.get("date").strftime("%d/%m/%Y"),
                                "forma": payment_method,
                                "monto": str(item.get("amount")),
                                "moneda": currency,
                            })
                        else:
                            payment_data.append({
                                "descripcion": payment.concept,
                                "fecha": item.get("date").strftime("%d/%m/%Y"),
                                "forma": payment_method,
                                "monto": str(item.get("amount")),
                                "moneda": currency,
                                "tipoCambio": str(round(record.foreign_rate, 2)),
                            })

                    return payment_data
                else:
                    return False
        except Exception as e:
            return False

    @api.depends('state', 'debit_origin_id', 'reversed_entry_id', 'document_digital_check_tfhka')
    def _compute_invisible_check(self):
        self.show_digital_invoice = True
        self.show_digital_note_debit = True
        self.show_digital_note_credit = True

        for record in self:
            if record.state == "posted":
                if record.move_type == "out_refund" and record.reversed_entry_id and record.reversed_entry_id.document_digital_check_tfhka and not record.document_digital_check_tfhka:
                    record.show_digital_note_credit = False

                elif record.debit_origin_id and record.debit_origin_id.document_digital_check_tfhka and not record.document_digital_check_tfhka:
                    record.show_digital_note_debit = False

                elif record.move_type == "out_invoice" and not record.debit_origin_id and not record.document_digital_check_tfhka:
                    record.show_digital_invoice = False