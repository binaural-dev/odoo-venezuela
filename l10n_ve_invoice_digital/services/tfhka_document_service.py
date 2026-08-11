import logging
import re

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


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
        document_number = client.get_last_document_number(company, document_type, series)
        try:
            document_number = int(document_number) + 1
        except (ValueError, TypeError):
            document_number = 1
        current_number = invoice.sequence_number

        if document_number != current_number and invoice.company_id.sequence_validation_tfhka:
            raise UserError(_("The document sequence in Odoo (%(odoo_seq)s) does not match the sequence in The Factory (%(factory_seq)s).Please check your numbering settings.", odoo_seq=current_number, factory_seq=document_number))

        document_number = str(document_number)

        return self.generate_document_data(invoice, document_number, document_type, series)

    def generate_document_data(self, invoice, document_number, document_type, series):
        document_identification = self._prepare_identification(invoice, document_type, document_number, series)
        seller = self._get_seller(invoice)
        buyer = self._get_fiscal_party(invoice)
        totals, foreign_totals = self._prepare_totals(invoice)
        details_items = self._prepare_detail_lines(invoice)
        additional_information = self._prepare_additional_information(invoice)

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

        payload["documentoElectronico"].update(self._prepare_extra_payload_values(invoice))
        _logger.info(f"---| {payload}")
        response = self.env["tfhka.api.client"].emit(invoice.company_id, payload)

        if response:
            self._register_success(invoice, response)
            return

    def _register_success(self, invoice, response):
        invoice.is_digitalized = True
        emission_date = fields.Datetime.now().strftime("%d/%m/%Y")
        invoice.message_post(
            body=_("Document successfully digitized on %(date)s", date=emission_date),
            message_type='comment',
        )
        num_control_tfhka = response.get("resultado").get("numeroControl")
        invoice.correlative = num_control_tfhka

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

            if not record.invoice_date:
                raise UserError(_("The invoice date is not defined."))

            # Multimoneda: si la factura es multimoneda con moneda de línea USD
            # (is_invoice_multi_currency_enabled), la moneda del documento es USD.
            if record.is_invoice_multi_currency_enabled():
                currency_tfhka = 'USD'
            else:
                currency_tfhka = record.company_id.currency_foreign_id.code_tfhka
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

    def _prepare_totals(self, invoice):
        for record in invoice:
            currency = record.company_id.currency_id.name
            totalIGTF = 0
            totalIGTF_VES = 0
            tax_totals = record.tax_totals

            totalIGTF = round(tax_totals.get("igtf", {}).get("igtf_amount", 0), 2)
            totalIGTF_VES = round(tax_totals.get("igtf", {}).get("foreign_igtf_amount", 0), 2)
            amounts = {}
            amounts_foreign = {}
            multi_currency = record.multi_currency_invoice

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

                taxes_subtotal, _dummy = self._prepare_tax_subtotals(record, currency)
                currency_tfhka_code = record.company_id.currency_id.code_tfhka

                # Multimoneda (patrón binaural_unidigital): si la factura es
                # multimoneda o trae tasa foránea, se reportan también los
                # TotalesOtraMoneda. Los montos se LEEN de Odoo (columnas
                # foreign_* de tax_totals), no se calculan dividiendo por la tasa.
                has_foreign_rate = bool(record.foreign_rate)
                if multi_currency or has_foreign_rate:
                    amounts_foreign["montoGravadoTotal"] = str(
                        round(
                            tax_totals.get('foreign_subtotal', 0) -
                            next(
                                (group['tax_group_base_amount'] for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])
                                if group.get('tax_group_name') in ("Exento", "IVA 0%")), 0
                            ), 2
                        )
                    )
                    amounts_foreign["montoExentoTotal"] = str(
                        round(
                            next((
                                group.get('tax_group_base_amount', 0)
                                for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])
                                if group.get('tax_group_name') in ("Exento", "IVA 0%")
                            ), 0), 2)
                    )
                    amounts_foreign["subtotal"] = str(round(tax_totals.get("foreign_amount_untaxed", 0), 2))
                    amounts_foreign["subtotalAntesDescuento"] = str(round(tax_totals.get("foreign_subtotal", 0), 2))
                    amounts_foreign["totalAPagar"] = str(round(tax_totals.get("foreign_amount_total_igtf", 0), 2))
                    amounts_foreign["totalIVA"] = round(sum(group.get('tax_group_amount', 0) for group in tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', [])), 2)
                    amounts_foreign["montoTotalConIVA"] = str(round(tax_totals.get("foreign_amount_total", 0), 2))
                    amounts_foreign["totalDescuento"] = str(abs(round(tax_totals.get("foreign_discount_amount", 0), 2)))
                    taxes_subtotal, taxes_subtotal_foreign = self._prepare_tax_subtotals(record, currency, multi_currency=True)
                    foreign_currency_code = record.company_id.currency_foreign_id.code_tfhka
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

                taxes_subtotal, taxes_subtotal_foreign = self._prepare_tax_subtotals(record, currency)
                currency = record.company_id.currency_foreign_id.code_tfhka
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
            payment_forms = self._prepare_payments(record)

            if payment_forms:
                if len(payment_forms) > 5:
                    raise UserError(_("The maximum number of payment methods is 5. Please check your payment methods."))
                if any(not method.get('forma') for method in payment_forms):
                    raise ValidationError(_("The payment method code is not configured in the journal."))
                totals["formasPago"] = payment_forms

            if amounts_foreign:
                foreign_totals = {
                    "moneda": foreign_currency_code or currency,
                    "tipoCambio": "{:.4f}".format(record.foreign_rate),
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

    def _prepare_tax_subtotals(self, invoice, currency, multi_currency=False):
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
        for record in invoice:
            if currency in ("VEF", "VES") and not multi_currency:
                for tax_totals in record.tax_totals.get('groups_by_subtotal', {}).get('Subtotal', []):
                    tax_subtotals.append({
                        "codigoTotalImp": tax_code[tax_totals.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_totals.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_totals.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_totals.get('tax_group_amount'), 2)),
                    })
                return tax_subtotals, tax_subtotals_foreign
            elif multi_currency:
                # Multimoneda: impuestos en la moneda base (groups_by_subtotal) y
                # en la moneda alterna (groups_by_foreign_subtotal). Ambos se LEEN
                # de Odoo; no se calcula nada dividiendo por la tasa.
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
                for tax_line in record.tax_totals.get('groups_by_foreign_subtotal', {}).get('Subtotal', []):
                    tax_subtotals_foreign.append({
                        "codigoTotalImp": tax_code[tax_line.get('tax_group_name')],
                        "alicuotaImp": tax_rate[tax_line.get('tax_group_name')],
                        "baseImponibleImp": str(round(tax_line.get('tax_group_base_amount'), 2)),
                        "valorTotalImp": str(round(tax_line.get('tax_group_amount'), 2)),
                    })
                if record.tax_totals.get('igtf', {}).get('apply_igtf'):
                    igtf = record.tax_totals.get('igtf', {})
                    tax_subtotals_foreign.append({
                        "codigoTotalImp": "IGTF",
                        "alicuotaImp": tax_rate.get(igtf.get('name'), "3.0"),
                        "baseImponibleImp": str(round(igtf.get('foreign_igtf_base_amount'), 2)),
                        "valorTotalImp": str(round(igtf.get('foreign_igtf_amount'), 2)),
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

                codigo_impuesto = tax_mapping.get(tax_rate)
                if codigo_impuesto is None:
                    raise UserError(_(
                        "The tax rate %(rate)s%% on product '%(product)s' is not supported "
                        "by TFHKA digitalization (allowed rates: 0, 8, 16, 31).",
                        rate=tax_rate, product=line.product_id.display_name,
                    ))

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
                    "codigoImpuesto": codigo_impuesto,
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

    def _get_payment_type(self, invoice):
        for record in invoice:
            if record.invoice_payment_term_id.line_ids.nb_days > 0:
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
                tipo_cambio = None
            else:
                currency_code = invoice.company_id.currency_foreign_id.code_tfhka
                if invoice.company_id.currency_id.name in ('VEF', 'VES'):
                    currency_code = invoice.company_id.currency_id.code_tfhka
                tipo_cambio = None
        else:
            # Pago en moneda extranjera: se incluye el tipo de cambio.
            currency_code = payment_currency
            tipo_cambio = "{:.4f}".format(payment_id.foreign_rate)

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

    def _prepare_additional_information(self, invoice):
        additional_information = []
        # for record in invoice:
        #     if record.guide_number:
        #         additional_information.append({
        #             "campo": "numeroGuia",
        #             "valor": str(record.guide_number),
        #         })

        return additional_information
