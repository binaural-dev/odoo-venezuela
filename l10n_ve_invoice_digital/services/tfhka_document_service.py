import logging
import re

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Monedas que Odoo puede tener configuradas para el bolívar.
VES_CURRENCY_NAMES = ("VEF", "VES")

# Grupos de impuestos que TFHKA reporta como exentos.
EXEMPT_TAX_GROUPS = ("Exento", "IVA 0%")

# Mapeo de grupo de impuesto de Odoo -> código/alícuota de TFHKA.
TFHKA_TAX_CODE = {
    "IVA 8%": "R",
    "IVA 16%": "G",
    "IVA 31%": "A",
    "Exento": "E",
    "IVA 0%": "E",
}
TFHKA_TAX_RATE = {
    "IVA 8%": "8.0",
    "IVA 16%": "16.0",
    "IVA 31%": "31.0",
    "Exento": "0.0",
    "IVA 0%": "0.0",
    "3.0 %": "3.0",
}


class TfhkaDocumentService(models.AbstractModel):
    """Arma y envía los documentos de venta (factura/NC/ND) a TFHKA.

    Paralelo a ``unidigital.document.service``: métodos ``_prepare_*``/``_get_*``
    que construyen cada sección del payload a partir de la factura, un
    ``_prepare_document_payload`` que compone todo y un ``send_document`` que
    orquesta el envío. El transporte HTTP lo hace ``tfhka.api.client``
    (``emit`` / ``query_numbering`` / ``get_last_document_number``), al que la
    compañía se pasa explícita. Extensible vía el hook
    ``_prepare_extra_payload_values``.
    """

    _name = "tfhka.document.service"
    _inherit = "tfhka.service.base"
    _description = "TFHKA Document Service"

    # ------------------------------------------------------------------
    # Tipo de documento / serie
    # ------------------------------------------------------------------

    def _get_document_type(self, invoice):
        document_type = ""
        if invoice.move_type == "out_invoice":
            document_type = "03" if invoice.debit_origin_id else "01"
        elif invoice.move_type == "out_refund" and invoice.reversed_entry_id:
            document_type = "02"
        return document_type

    def _get_series(self, invoice):
        series = ""
        if invoice.company_id.group_sales_invoicing_series and invoice.journal_id.series_correlative_sequence_id:
            if invoice.journal_id.sequence_id and invoice.journal_id.sequence_id.prefix:
                series = re.sub(r'[^a-zA-Z0-9]', '', invoice.journal_id.sequence_id.prefix)
            else:
                raise UserError(_("The selected series is not configured"))
        return series

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def send_document(self, invoice):
        invoice.ensure_one()
        if not invoice.company_id.invoice_digital_tfhka:
            return

        document_type = self._get_document_type(invoice)
        if not document_type:
            return

        series = self._get_series(invoice)

        company = invoice.company_id
        client = self.env["tfhka.api.client"]

        client.query_numbering(company, series)

        # Secuencia: en modo "pago primero" (o con la sincronización desactivada)
        # se usa el correlativo local de Odoo; en el modo normal se ADOPTA el
        # correlativo de The Factory (último + 1) y luego se sincroniza el diario.
        if company.digitalization_with_payment_tfhka or not company.sequence_validation_tfhka:
            document_number = invoice.sequence_number
        else:
            last = client.get_last_document_number(company, document_type, series)
            try:
                document_number = int(last) + 1
            except (ValueError, TypeError):
                document_number = invoice.sequence_number or 1

        document_number = str(document_number)

        return self.generate_document_data(invoice, document_number, document_type, series)

    def generate_document_data(self, invoice, document_number, document_type, series):
        document_identification = self._prepare_identification(invoice, document_type, document_number, series)
        seller = self._get_seller(invoice)
        buyer = self._get_fiscal_party(invoice)
        totals, foreign_totals = self._prepare_totals(invoice)
        details_items = self._prepare_detail_lines(invoice)
        additional_information = self._prepare_additional_information(invoice)
        dispatch_guide_reference = self._get_dispatch_guide_reference(invoice)

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
        if dispatch_guide_reference:
            payload["documentoElectronico"]["FacturaGuia"] = dispatch_guide_reference

        payload["documentoElectronico"].update(self._prepare_extra_payload_values(invoice))
        response = self.env["tfhka.api.client"].emit(invoice.company_id, payload)

        if response:
            self._register_success(invoice, response, document_number)
            return

    def _register_success(self, invoice, response, document_number):
        invoice.is_digitalized = True
        emission_date = fields.Datetime.now().strftime("%d/%m/%Y")
        invoice.message_post(
            body=_("Document successfully digitized on %(date)s") % {"date": emission_date},
            message_type='comment',
        )
        num_control_tfhka = response.get("resultado").get("numeroControl")
        invoice.correlative = num_control_tfhka

        # Sincronización de secuencia: si se adoptó el correlativo de The Factory
        # (modo normal) y difiere del de Odoo, se avanza el diario y se renombra
        # la factura al número asignado por The Factory.
        company = invoice.company_id
        if (
            not company.digitalization_with_payment_tfhka
            and company.sequence_validation_tfhka
            and str(invoice.sequence_number) != str(document_number)
        ):
            try:
                number = int(document_number)
                field = self._get_sequence_field(invoice)
                invoice.journal_id.sudo().write({field: number + 1})
                invoice.name = self._get_document_name(invoice, number)
            except Exception as error:
                _logger.error("No se pudo sincronizar la secuencia del diario TFHKA: %s", error)

    def _get_sequence_field(self, invoice):
        if invoice.move_type == "out_refund":
            return "refund_sequence_number_next"
        return "sequence_number_next"

    def _get_document_name(self, invoice, number):
        journal = invoice.journal_id
        sequence = (
            journal.refund_sequence_id
            if invoice.move_type == "out_refund" and journal.refund_sequence_id
            else journal.sequence_id
        )
        prefix = sequence.prefix or ""
        return f"{prefix}{str(number).zfill(8)}"

    def _prepare_extra_payload_values(self, invoice):
        """Hook de extensión: valores extra del payload. Por defecto vacío."""
        return {}

    # ------------------------------------------------------------------
    # Secciones del payload
    # ------------------------------------------------------------------

    def _prepare_identification(self, invoice, document_type, document_number, series):
        for record in invoice:
            now_local = self._get_emission_datetime(record)
            emission_time = now_local.strftime("%I:%M:%S %p").lower()
            emission_date = now_local.date()
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

                if record.ref and ',' in record.ref:
                    affected_invoice_comment = record.ref.split(',', 1)[1].strip()

            # O19: invoice_date_display es la fecha fiscal del documento
            # (invoice_date quedó reservada al cálculo de la tasa de cambio).
            if not record.invoice_date_display:
                raise UserError(_("The invoice date is not defined."))

            # Multimoneda: si la factura es multimoneda con moneda de línea USD
            # (is_invoice_multi_currency_enabled), la moneda del documento es USD.
            if record.is_invoice_multi_currency_enabled():
                currency_tfhka = 'USD'
            else:
                currency_tfhka = record.company_id.foreign_currency_id.code_tfhka
                if record.company_id.currency_id.name in ('VEF', 'VES'):
                    currency_tfhka = record.company_id.currency_id.code_tfhka

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
                "tipoDePago": self._get_payment_type(invoice),
                "serie": series,
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": currency_tfhka,
                "transaccionId": "",
                "urlPdf": ""
            }

    # ------------------------------------------------------------------
    # Lectura de tax_totals (estructura Odoo 19)
    # ------------------------------------------------------------------

    def _get_tax_groups(self, invoice):
        """Lista plana de grupos de impuestos de ``tax_totals``.

        O19 reemplazó ``groups_by_subtotal['Subtotal']`` por ``subtotals``, una
        lista de cubetas de subtotal donde cada una lleva sus ``tax_groups``.
        Se aplanan porque TFHKA reporta un único nivel de impuestos.
        """
        tax_totals = invoice.tax_totals or {}
        groups = []
        for subtotal in tax_totals.get("subtotals", []):
            groups.extend(subtotal.get("tax_groups", []))
        return groups

    def _get_discount_amount(self, invoice, foreign=False):
        """Descuento total del documento.

        O19 solo expone ``formatted_total_discount`` (cadena ya formateada por
        ``formatLang``), no un numérico, así que se recalcula desde las líneas.
        """
        total = 0.0
        for line in invoice.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
            price = line.foreign_price if foreign else line.price_unit
            total += price * line.quantity * (line.discount or 0.0) / 100.0
        return total

    def _get_igtf_amounts(self, invoice):
        """Importes de IGTF en moneda base y en moneda alterna.

        ``tax_totals['igtf']['foreign_igtf_amount']`` no es fiable en O19:
        ``l10n_ve_igtf`` lo sobreescribe con el valor de la variante free-form
        por un shadowing de variable. El importe en divisa se recalcula desde
        su base y el porcentaje de IGTF de la compañía.
        """
        tax_totals = invoice.tax_totals or {}
        igtf = tax_totals.get("igtf") or {}
        percentage = (invoice.company_id.igtf_percentage or 0.0) / 100.0
        base = igtf.get("igtf_base_amount", 0.0) or 0.0
        total = tax_totals.get("total_amount_currency", 0.0) or 0.0
        return {
            "apply": igtf.get("apply_igtf", False),
            "name": igtf.get("name"),
            "percentage": percentage,
            "base": base,
            "amount": igtf.get("igtf_amount", 0.0) or 0.0,
            # Fracción del total sujeta a IGTF. Se guarda la PROPORCIÓN y no el
            # importe en divisa porque ``foreign_igtf_base_amount`` no es
            # comparable con las claves ``*_amount_foreign_currency``: cuál de
            # las dos monedas llama "foreign" cada módulo depende de la
            # configuración de la compañía, y mezclarlas sumaba un IGTF en
            # bolívares a un total en dólares.
            "ratio": (base / total) if total else 0.0,
        }

    def _get_igtf_block(self, invoice, foreign=False):
        """Base e importe de IGTF expresados en la moneda de un bloque."""
        igtf = self._get_igtf_amounts(invoice)
        if not igtf["apply"]:
            return 0.0, 0.0
        if not foreign:
            return igtf["base"], igtf["amount"]
        total_foreign = (invoice.tax_totals or {}).get("total_amount_foreign_currency", 0.0) or 0.0
        base = total_foreign * igtf["ratio"]
        return base, base * igtf["percentage"]

    def _should_report_foreign_totals(self, invoice):
        """Criterio ÚNICO para adjuntar el bloque ``totalesOtraMoneda``.

        En 17.0 convivían tres criterios distintos (``foreign_rate`` truthy,
        ``multi_currency_invoice`` crudo y ``is_invoice_multi_currency_enabled``),
        lo que producía payloads incoherentes entre cabecera, totales y líneas.
        """
        return bool(invoice.is_invoice_multi_currency_enabled() or invoice.foreign_rate)

    def _build_amounts(self, invoice, foreign=False):
        """Bloque de totales en una de las dos monedas del documento.

        ``foreign=False`` -> moneda del documento (claves ``*_amount_currency``).
        ``foreign=True``  -> moneda alterna (claves ``*_amount_foreign_currency``
        que añade ``l10n_ve_accountant`` sobre el ``tax_totals`` del core).
        """
        tax_totals = invoice.tax_totals or {}
        groups = self._get_tax_groups(invoice)

        if foreign:
            base_key, tax_key = "base_amount_foreign_currency", "tax_amount_foreign_currency"
            total_key = "total_amount_foreign_currency"
        else:
            base_key, tax_key = "base_amount_currency", "tax_amount_currency"
            total_key = "total_amount_currency"

        exempt_base = sum(
            group.get(base_key, 0.0) for group in groups
            if group.get("group_name") in EXEMPT_TAX_GROUPS
        )
        taxed_base = sum(
            group.get(base_key, 0.0) for group in groups
            if group.get("group_name") not in EXEMPT_TAX_GROUPS
        )
        total_tax = sum(group.get(tax_key, 0.0) for group in groups)
        untaxed = taxed_base + exempt_base
        discount = self._get_discount_amount(invoice, foreign=foreign)
        total_with_tax = tax_totals.get(total_key, 0.0) or 0.0

        _igtf_base, igtf_amount = self._get_igtf_block(invoice, foreign=foreign)

        return {
            "montoGravadoTotal": str(round(taxed_base, 2)),
            "montoExentoTotal": str(round(exempt_base, 2)),
            "subtotal": str(round(untaxed, 2)),
            "subtotalAntesDescuento": str(round(untaxed + discount, 2)),
            "totalAPagar": str(round(total_with_tax + igtf_amount, 2)),
            "totalIVA": str(round(total_tax, 2)),
            "montoTotalConIVA": str(round(total_with_tax, 2)),
            "totalDescuento": str(abs(round(discount, 2))),
        }

    def _prepare_totals(self, invoice):
        totals, foreign_totals = {}, False
        for record in invoice:
            company = record.company_id
            company_is_ves = company.currency_id.name in VES_CURRENCY_NAMES
            # IGTF de cada bloque en SU moneda: sumar el de un bloque al total
            # del otro descuadra totalAPagar.
            _b, igtf_doc = self._get_igtf_block(record, foreign=False)
            _b, igtf_alt = self._get_igtf_block(record, foreign=True)
            # El bloque en bolívares es el del documento si la compañía es VES,
            # y el alterno en caso contrario.
            igtf_ves = igtf_doc if company_is_ves else igtf_alt
            report_foreign = self._should_report_foreign_totals(record)

            if company_is_ves:
                # Compañía en bolívares: el documento va en la moneda base y la
                # divisa (si aplica) en el bloque totalesOtraMoneda.
                amounts = self._build_amounts(record, foreign=False)
                taxes_subtotal = self._prepare_tax_subtotals(
                    record, foreign=False, include_igtf=report_foreign
                )
                if report_foreign:
                    amounts_foreign = self._build_amounts(record, foreign=True)
                    taxes_subtotal_foreign = self._prepare_tax_subtotals(
                        record, foreign=True, include_igtf=True
                    )
                    foreign_currency_code = company.foreign_currency_id.code_tfhka
                else:
                    amounts_foreign = {}
                    taxes_subtotal_foreign = []
                    foreign_currency_code = None
            else:
                # Compañía en divisa: se invierten los papeles — el documento va
                # en la divisa y el bloque alterno lleva los importes en bolívares.
                amounts = self._build_amounts(record, foreign=True)
                amounts_foreign = self._build_amounts(record, foreign=False)
                taxes_subtotal = self._prepare_tax_subtotals(
                    record, foreign=True, include_igtf=True
                )
                taxes_subtotal_foreign = self._prepare_tax_subtotals(
                    record, foreign=False, include_igtf=True
                )
                foreign_currency_code = company.currency_id.code_tfhka

            # nroItems debe cuadrar con detallesItems, que solo lleva líneas de
            # producto: contar invoice_line_ids incluiría secciones y notas.
            item_count = len(record.invoice_line_ids.filtered(
                lambda l: l.display_type == "product"
            ))

            totals = {
                "nroItems": str(item_count),
                "montoGravadoTotal": amounts["montoGravadoTotal"],
                "montoExentoTotal": amounts["montoExentoTotal"],
                "subtotal": amounts["subtotal"],
                "subtotalAntesDescuento": amounts["subtotalAntesDescuento"],
                "totalAPagar": amounts["totalAPagar"],
                "totalIVA": amounts["totalIVA"],
                "montoTotalConIVA": amounts["montoTotalConIVA"],
                "totalDescuento": amounts["totalDescuento"],
                "impuestosSubtotal": taxes_subtotal,
                "totalIGTF": str(round(igtf_doc, 2)),
                "totalIGTF_VES": str(round(igtf_ves, 2)),
            }
            # Cuadro de pago: el bloque formasPago solo se adjunta cuando el
            # usuario activó "Mostrar cuadro de pago" en la factura.
            if record.show_payment_box:
                payment_forms = self._prepare_payments(record)

                if payment_forms:
                    if len(payment_forms) > 5:
                        raise UserError(_("The maximum number of payment methods is 5. Please check your payment methods."))
                    if any(not method.get('forma') for method in payment_forms):
                        raise ValidationError(_("The payment method code is not configured in the journal."))
                    totals["formasPago"] = payment_forms

            if amounts_foreign:
                foreign_totals = {
                    "moneda": foreign_currency_code,
                    "tipoCambio": "{:.4f}".format(record.foreign_rate),
                    "montoGravadoTotal": amounts_foreign["montoGravadoTotal"],
                    "montoExentoTotal": amounts_foreign["montoExentoTotal"],
                    "subtotal": amounts_foreign["subtotal"],
                    "subtotalAntesDescuento": amounts_foreign["subtotalAntesDescuento"],
                    "totalAPagar": amounts_foreign["totalAPagar"],
                    "totalIVA": amounts_foreign["totalIVA"],
                    "montoTotalConIVA": amounts_foreign["montoTotalConIVA"],
                    "totalDescuento": amounts_foreign["totalDescuento"],
                    "totalIGTF": str(round(igtf_alt, 2)),
                    "totalIGTF_VES": str(round(igtf_ves, 2)),
                    "impuestosSubtotal": taxes_subtotal_foreign,
                }
            else:
                foreign_totals = False
        return totals, foreign_totals

    def _prepare_tax_subtotals(self, invoice, foreign=False, include_igtf=False):
        """Detalle de impuestos (``impuestosSubtotal``) en una de las monedas.

        Devuelve una lista; en 17.0 devolvía una tupla (base, alterna) y el
        llamador decidía cuál usar según tres criterios distintos. Ahora cada
        moneda se pide por separado con ``foreign``.
        """
        invoice.ensure_one()
        if foreign:
            base_key, tax_key = "base_amount_foreign_currency", "tax_amount_foreign_currency"
        else:
            base_key, tax_key = "base_amount_currency", "tax_amount_currency"

        tax_subtotals = []
        for group in self._get_tax_groups(invoice):
            group_name = group.get("group_name")
            if group_name not in TFHKA_TAX_CODE:
                raise UserError(
                    _(
                        "The tax group '%(group)s' has no TFHKA equivalent configured. "
                        "Please review the taxes applied to this document."
                    )
                    % {"group": group_name}
                )
            tax_subtotals.append({
                "codigoTotalImp": TFHKA_TAX_CODE[group_name],
                "alicuotaImp": TFHKA_TAX_RATE[group_name],
                "baseImponibleImp": str(round(group.get(base_key, 0.0), 2)),
                "valorTotalImp": str(round(group.get(tax_key, 0.0), 2)),
            })

        if include_igtf:
            igtf = self._get_igtf_amounts(invoice)
            if igtf["apply"]:
                igtf_base, igtf_amount = self._get_igtf_block(invoice, foreign=foreign)
                tax_subtotals.append({
                    "codigoTotalImp": "IGTF",
                    "alicuotaImp": TFHKA_TAX_RATE.get(igtf["name"], "3.0"),
                    "baseImponibleImp": str(round(igtf_base, 2)),
                    "valorTotalImp": str(round(igtf_amount, 2)),
                })

        return tax_subtotals

    def _prepare_detail_lines(self, invoice):
        item_details = []
        line_number = 1
        for record in invoice:
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

                # Multimoneda: si la factura es multimoneda (moneda de línea USD)
                # o la moneda base no es VES, los montos de línea van en la
                # moneda alterna (foreign_price/foreign_subtotal).
                if not record.is_invoice_multi_currency_enabled() and record.company_id.currency_id.name in ("VEF", "VES"):
                    base_price = line.price_unit
                    base_subtotal = line.price_subtotal
                else:
                    base_price = line.foreign_price
                    base_subtotal = line.foreign_subtotal

                discount_factor = (line.discount or 0.0) / 100.0
                unit_price = round(base_price, 2)
                discount_unit = round(base_price * discount_factor, 2)
                unit_price_discount = round(base_price - discount_unit, 2)
                discount_amount = round(base_price * discount_factor * line.quantity, 2)
                item_price = round(base_subtotal, 2)
                price_before_discount = round(base_price * line.quantity, 2)

                vat = round(item_price * tax_rate / 100.0, 2)
                total_item_value = round(item_price + vat, 2)

                tax_code = tax_mapping.get(tax_rate)
                if tax_code is None:
                    raise UserError(
                        _(
                            "The tax rate %(rate)s%% on product '%(product)s' is not supported "
                            "by TFHKA digitalization (allowed rates: 0, 8, 16, 31)."
                        )
                        % {"rate": tax_rate, "product": line.product_id.display_name}
                    )

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
                    "codigoImpuesto": tax_code,
                    "tasaIVA": str(round(tax_rate, 2)),
                    "valorIVA": str(vat),
                    "valorTotalItem": str(total_item_value),
                })
                line_number += 1
        return item_details

    def _get_seller(self, invoice):
        for record in invoice:
            if "seller_id" in record._fields and record.seller_id:
                return {
                    "codigo": str(record.seller_id.id),
                    "nombre": record.seller_id.name,
                    "numCajero": ""
                }
            else:
                return False

    def _get_dispatch_guide_reference(self, invoice):
        """Referencia a la guia de despacho asociada, cuando la factura
        proviene de una (campo guide_number de l10n_ve_stock_account)."""
        for record in invoice:
            if "guide_number" in record._fields and record.guide_number:
                return {
                    "TipoDocumento": "04",
                    "NumeroDocumento": record.guide_number,
                }
            else:
                return False

    def _get_payment_type(self, invoice):
        for record in invoice:
            # nb_days sobre un recordset de varias líneas lanza excepción: un
            # término de pago con más de un plazo es perfectamente válido.
            terms = record.invoice_payment_term_id.line_ids
            if any(term.nb_days > 0 for term in terms):
                return "Crédito"
            else:
                return "Inmediato"

    def _prepare_payments(self, invoice):
        try:
            payment_data = []
            for record in invoice:
                content_data = record.invoice_payments_widget.get("content", [])
                if content_data:
                    for item in content_data:
                        payment = self._get_payment(item.get('account_payment_id'))

                        if not payment:
                            continue

                        payment_info = self._build_payment_info(record, payment)
                        payment_data.append(payment_info)
                    return payment_data
            return False
        except Exception as e:
            _logger.error("Error processing payment methods: %s", e)
            return False

    def _get_payment(self, account_payment_id):
        return self.env['account.payment'].search([('id', '=', account_payment_id)])

    def _build_payment_info(self, invoice, payment):
        payment_id = self.env['account.payment'].search([('id', '=', payment.id)])
        payment_currency = payment_id.currency_id.name if payment_id.currency_id else "VES"
        payment_method = payment_id.journal_id.payment_method_code if payment_id.journal_id.payment_method_code else False
        multi_currency = invoice.is_invoice_multi_currency_enabled()

        if payment_currency == "VEF" or payment_currency == "VES":
            if multi_currency:
                # Multimoneda: el pago en VES se reporta como moneda local.
                currency_code = invoice.company_id.currency_id.code_tfhka
                exchange_rate = None
            else:
                currency_code = invoice.company_id.foreign_currency_id.code_tfhka
                if invoice.company_id.currency_id.name in ('VEF', 'VES'):
                    currency_code = invoice.company_id.currency_id.code_tfhka
                exchange_rate = None
        else:
            # Pago en moneda extranjera: se incluye el tipo de cambio.
            currency_code = payment_currency
            exchange_rate = "{:.4f}".format(payment_id.foreign_rate)

        payment_info = {
            "descripcion": payment_method.description if payment_method else "",
            "fecha": payment_id.date.strftime("%d/%m/%Y") if payment_id.date else "",
            "forma": payment_method.code if payment_method else "",
            "monto": str(round(payment_id.amount, 2)),
            "moneda": currency_code,
        }

        if exchange_rate:
            payment_info["tipoCambio"] = exchange_rate

        return payment_info

    def _prepare_additional_information(self, invoice):
        additional_information = []
        # for record in invoice:
        #     if record.guide_number:
        #         additional_information.append({
        #             "campo": "numeroGuia",
        #             "valor": str(record.guide_number),
        #         })

        return additional_information
