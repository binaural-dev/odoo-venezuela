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
        currency_context = self._get_currency_context(invoice)

        document_identification = self._prepare_identification(
            invoice, document_type, document_number, series, currency_context
        )
        seller = self._get_seller(invoice)
        buyer = self._get_fiscal_party(invoice)
        totals, foreign_totals = self._prepare_totals(invoice, currency_context)
        details_items = self._prepare_detail_lines(invoice, currency_context)
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
    # Contexto de moneda
    # ------------------------------------------------------------------

    def _get_document_foreign_currency(self, invoice):
        """Divisa en juego para esta factura, o un recordset vacío si no hay.

        ``account_invoice_pricelist`` fuerza ``currency_id`` a la moneda de la
        tarifa, así que la moneda de la factura ES la de la tarifa. Se cae a
        ``_get_pricelist_currency`` (misma cadena que usa el modelo para el
        dominio de ``line_currency_id``) para registros sin tarifa.

        Fallback final: ``line_currency_id``. Cubre el modo pago-primero donde
        la tarifa está en la moneda base pero el usuario eligió una divisa en
        el selector (activado por un pago en divisa conciliado). En ese caso ni
        ``currency_id`` ni ``_get_pricelist_currency`` difieren de la base, así
        que la única fuente de verdad es la elección explícita del campo.
        """
        base_currency = invoice.company_id.currency_id
        if invoice.currency_id and invoice.currency_id != base_currency:
            return invoice.currency_id
        pricelist_currency = invoice._get_pricelist_currency()
        if pricelist_currency and pricelist_currency != base_currency:
            return pricelist_currency
        # Modo pago-primero: tarifa en moneda base, divisa viene de line_currency_id.
        if invoice.line_currency_id and invoice.line_currency_id != base_currency:
            return invoice.line_currency_id
        return self.env["res.currency"]

    def _get_currency_context(self, invoice):
        """Resuelve en qué moneda va cada bloque del documento.

        Devuelve ``document_currency`` (cabecera, ``totales`` y
        ``detallesItems``), ``alt_currency`` (bloque ``totalesOtraMoneda``, vacío
        si el documento es de una sola moneda) y ``rate`` (bolívares por unidad
        de divisa, el ``tipoCambio``).

        Sin ``multi_currency_invoice`` el documento entero viaja en la moneda
        base de la compañía: el ajuste de compañía solo muestra el campo y la
        mera existencia de una tasa (``foreign_rate``, poblada en toda factura
        VE) no convierte el documento en bimoneda.
        """
        invoice.ensure_one()
        base_currency = invoice.company_id.currency_id
        foreign_currency = self._get_document_foreign_currency(invoice)
        empty_currency = self.env["res.currency"]

        if not self._should_report_foreign_totals(invoice):
            document_currency = base_currency
            alt_currency = empty_currency
        else:
            if not foreign_currency:
                raise UserError(
                    _(
                        "This invoice is flagged as multi-currency but its pricelist is "
                        "in the company base currency (%(currency)s), so there is no "
                        "second currency to report."
                    )
                    % {"currency": base_currency.name}
                )
            if not invoice.line_currency_id:
                raise UserError(
                    _(
                        "This invoice is flagged as multi-currency but no 'Line Currency' "
                        "has been selected."
                    )
                )
            document_currency = invoice.line_currency_id
            alt_currency = (
                foreign_currency if document_currency == base_currency else base_currency
            )

        rate = (
            self._resolve_foreign_rate(invoice, foreign_currency)
            if foreign_currency
            else 1.0
        )

        self._check_currency_codes(document_currency | alt_currency)

        return {
            "multi_currency": bool(alt_currency),
            "document_currency": document_currency,
            "alt_currency": alt_currency,
            "foreign_currency": foreign_currency,
            "rate": rate,
        }

    def _resolve_foreign_rate(self, invoice, foreign_currency):
        """Bolívares que vale una unidad de ``foreign_currency`` en esta factura.

        Si coincide con la moneda extranjera de la compañía se reutiliza
        ``invoice.foreign_rate``, que ya respeta la tasa fijada a mano. Para
        cualquier otra divisa (p. ej. EUR con la compañía en USD) se busca en la
        tabla de tasas a la fecha del documento, igual que hace
        ``binaural_unidigital._resolve_foreign_rate``.
        """
        company = invoice.company_id
        if company.foreign_currency_id and foreign_currency == company.foreign_currency_id:
            return invoice.foreign_rate or 1.0

        rate_date = invoice.invoice_date_display or invoice.invoice_date or invoice.date or fields.Date.today()
        rate_values = (
            self.env["res.currency.rate"]
            .with_company(company)
            .compute_rate(foreign_currency.id, rate_date)
        )
        rate = rate_values.get("foreign_rate")
        if not rate:
            raise UserError(
                _(
                    "No %(currency)s exchange rate found for %(date)s. Please configure "
                    "the currency rate before digitalizing this document."
                )
                % {"currency": foreign_currency.name, "date": rate_date}
            )
        return rate

    def _check_currency_codes(self, currencies):
        """Exige ``code_tfhka`` en toda moneda que vaya a viajar en el payload.

        Sin esto el documento sale con ``"moneda": false`` y The Factory lo
        rechaza sin explicar por qué; el campo se carga a mano en la ficha de la
        moneda y solo el bolívar viene sembrado.
        """
        missing = currencies.filtered(lambda currency: not currency.code_tfhka)
        if missing:
            raise UserError(
                _(
                    "The currency %(currencies)s has no 'Code TFHKA' configured. Set it "
                    "in Accounting > Configuration > Currencies before digitalizing this "
                    "document."
                )
                % {"currencies": ", ".join(missing.mapped("name"))}
            )

    def _convert_amount(self, invoice, amount, from_currency, to_currency, rate):
        """Convierte entre la moneda base y una divisa usando ``rate``.

        ``rate`` son bolívares por unidad de divisa, la misma convención que
        ``foreign_rate`` y ``res.currency.rate.compute_rate``.
        """
        if not amount or from_currency == to_currency:
            return amount
        base_currency = invoice.company_id.currency_id
        if to_currency == base_currency:
            return amount * rate
        if from_currency == base_currency:
            return amount / rate if rate else amount
        return amount

    def _get_amount_in_currency(self, invoice, currency, ctx, amount, source_currency=None):
        """Lleva un importe de la moneda de la factura a ``currency``."""
        source_currency = source_currency or invoice.currency_id
        return self._convert_amount(invoice, amount, source_currency, currency, ctx["rate"])

    def _get_tax_totals_keys(self, invoice, currency):
        """Sufijos de ``tax_totals`` que expresan los importes en ``currency``.

        ``tax_totals`` publica tres juegos de claves y con ellos se cubre todo
        caso real sin convertir a mano:

        * ``*_amount_currency``          -> moneda de la factura (= tarifa)
        * ``base_amount``/``tax_amount`` -> moneda de la compañía (VES)
        * ``*_amount_foreign_currency``  -> ``move.foreign_currency_id``

        Devuelve ``None`` si ninguno aplica; el llamador convierte con la tasa.
        """
        if currency == invoice.currency_id:
            return "base_amount_currency", "tax_amount_currency", "total_amount_currency"
        if currency == invoice.company_id.currency_id:
            return "base_amount", "tax_amount", "total_amount"
        if currency == invoice.foreign_currency_id:
            return (
                "base_amount_foreign_currency",
                "tax_amount_foreign_currency",
                "total_amount_foreign_currency",
            )
        return None

    # ------------------------------------------------------------------
    # Secciones del payload
    # ------------------------------------------------------------------

    def _prepare_identification(self, invoice, document_type, document_number, series, ctx=None):
        ctx = ctx or self._get_currency_context(invoice)
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

                affected_invoice_amount = self._get_affected_document_amount(
                    record.debit_origin_id, ctx
                )

                if record.ref and ',' in record.ref:
                    affected_invoice_comment = record.ref.split(',', 1)[1].strip()

            if record.reversed_entry_id:
                affected_invoice_number = str(record.reversed_entry_id.sequence_number)

                affected_invoice_date = record.reversed_entry_id.invoice_date.strftime("%d/%m/%Y") if record.reversed_entry_id.invoice_date else ""

                if record.reversed_entry_id.journal_id.series_correlative_sequence_id:
                    affected_invoice_series = record.reversed_entry_id.journal_id.sequence_id.prefix if record.reversed_entry_id.journal_id.sequence_id.prefix else ""

                affected_invoice_amount = self._get_affected_document_amount(
                    record.reversed_entry_id, ctx
                )

                if record.ref and ',' in record.ref:
                    affected_invoice_comment = record.ref.split(',', 1)[1].strip()

            # O19: invoice_date_display es la fecha fiscal del documento
            # (invoice_date quedó reservada al cálculo de la tasa de cambio).
            if not record.invoice_date_display:
                raise UserError(_("The invoice date is not defined."))

            # La moneda del encabezado es la del contexto, sin literales: cubre
            # VES, USD, EUR o cualquier otra moneda con code_tfhka cargado.
            currency_tfhka = ctx["document_currency"].code_tfhka

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

    def _get_affected_document_amount(self, affected_document, ctx):
        """``montoFacturaAfectada`` de una NC/ND, en la moneda del documento.

        Se toma el total CON IGTF del documento afectado, que es lo que el
        cliente pagó. 17.0 elegía la clave según la moneda de la compañía, con
        lo que una factura en divisa reportaba el monto afectado en bolívares.
        """
        tax_totals = affected_document.tax_totals or {}
        document_currency = ctx["document_currency"]

        if document_currency == affected_document.company_id.currency_id:
            amount = tax_totals.get("foreign_amount_total_igtf")
            if amount is None:
                amount = affected_document.amount_total_signed
        else:
            amount = tax_totals.get("amount_total_igtf")
            if amount is None:
                amount = affected_document.amount_total
            if document_currency != affected_document.currency_id:
                amount = self._get_amount_in_currency(
                    affected_document, document_currency, ctx, amount
                )

        return str(round(abs(amount), 2))

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

    def _get_discount_amount(self, invoice, currency, ctx):
        """Descuento total del documento, expresado en ``currency``.

        O19 solo expone ``formatted_total_discount`` (cadena ya formateada por
        ``formatLang``), no un numérico, así que se recalcula desde las líneas.
        Las líneas están en la moneda de la factura, de ahí la conversión.
        """
        total = 0.0
        for line in invoice.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
            total += line.price_unit * line.quantity * (line.discount or 0.0) / 100.0
        return self._get_amount_in_currency(invoice, currency, ctx, total)

    def _get_igtf_block(self, invoice, currency, ctx):
        """Base e importe de IGTF expresados en ``currency``.

        ``l10n_ve_igtf`` publica el IGTF en dos monedas: las claves ``igtf_*``
        van en la moneda de la factura y las ``foreign_igtf_*`` en la moneda de
        la COMPAÑÍA (no en ``company.foreign_currency_id``, pese al nombre; ver
        ``l10n_ve_igtf/models/account_tax.py``). Con eso se cubren las dos caras
        del documento sin recalcular nada a partir de proporciones.
        """
        igtf = (invoice.tax_totals or {}).get("igtf") or {}
        if not igtf.get("apply_igtf"):
            return 0.0, 0.0

        if currency == invoice.company_id.currency_id:
            return (
                currency.round(igtf.get("foreign_igtf_base_amount", 0.0) or 0.0),
                currency.round(igtf.get("foreign_igtf_amount", 0.0) or 0.0),
            )

        base = igtf.get("igtf_base_amount", 0.0) or 0.0
        amount = igtf.get("igtf_amount", 0.0) or 0.0
        if currency == invoice.currency_id:
            return currency.round(base), currency.round(amount)
        return (
            currency.round(self._get_amount_in_currency(invoice, currency, ctx, base)),
            currency.round(self._get_amount_in_currency(invoice, currency, ctx, amount)),
        )

    def _should_report_foreign_totals(self, invoice):
        """Criterio ÚNICO para adjuntar el bloque ``totalesOtraMoneda``.

        Es el flag de la factura y solo el flag. En 17.0 convivían tres
        criterios distintos —entre ellos ``foreign_rate`` truthy, que está
        poblado en TODA factura venezolana—, así que en la práctica cualquier
        factura salía bimoneda por el mero hecho de tener activada la opción en
        la compañía. El ajuste de compañía únicamente muestra el campo.
        """
        return bool(invoice.multi_currency_invoice)

    def _build_amounts(self, invoice, currency, ctx):
        """Bloque de totales expresado en ``currency``.

        Se leen del ``tax_totals`` las claves que ya vienen en esa moneda
        (ver ``_get_tax_totals_keys``); si ninguna aplica se convierte desde la
        moneda de la factura con la tasa del contexto.
        """
        tax_totals = invoice.tax_totals or {}
        groups = self._get_tax_groups(invoice)

        keys = self._get_tax_totals_keys(invoice, currency)
        needs_conversion = keys is None
        if needs_conversion:
            keys = ("base_amount_currency", "tax_amount_currency", "total_amount_currency")
        base_key, tax_key, total_key = keys

        exempt_base = sum(
            group.get(base_key, 0.0) for group in groups
            if group.get("group_name") in EXEMPT_TAX_GROUPS
        )
        taxed_base = sum(
            group.get(base_key, 0.0) for group in groups
            if group.get("group_name") not in EXEMPT_TAX_GROUPS
        )
        total_tax = sum(group.get(tax_key, 0.0) for group in groups)
        total_with_tax = tax_totals.get(total_key, 0.0) or 0.0

        if needs_conversion:
            exempt_base = self._get_amount_in_currency(invoice, currency, ctx, exempt_base)
            taxed_base = self._get_amount_in_currency(invoice, currency, ctx, taxed_base)
            total_tax = self._get_amount_in_currency(invoice, currency, ctx, total_tax)
            total_with_tax = self._get_amount_in_currency(invoice, currency, ctx, total_with_tax)

        untaxed = taxed_base + exempt_base
        discount = self._get_discount_amount(invoice, currency, ctx)

        _igtf_base, igtf_amount = self._get_igtf_block(invoice, currency, ctx)

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

    def _prepare_totals(self, invoice, ctx=None):
        ctx = ctx or self._get_currency_context(invoice)
        totals, foreign_totals = {}, False
        for record in invoice:
            document_currency = ctx["document_currency"]
            alt_currency = ctx["alt_currency"]
            base_currency = record.company_id.currency_id

            # IGTF de cada bloque en SU moneda: sumar el de un bloque al total
            # del otro descuadra totalAPagar. totalIGTF_VES va siempre en la
            # moneda base, sea cual sea la moneda del documento.
            _b, igtf_doc = self._get_igtf_block(record, document_currency, ctx)
            _b, igtf_ves = self._get_igtf_block(record, base_currency, ctx)

            amounts = self._build_amounts(record, document_currency, ctx)
            taxes_subtotal = self._prepare_tax_subtotals(
                record, document_currency, ctx, include_igtf=True
            )

            if alt_currency:
                _b, igtf_alt = self._get_igtf_block(record, alt_currency, ctx)
                amounts_foreign = self._build_amounts(record, alt_currency, ctx)
                taxes_subtotal_foreign = self._prepare_tax_subtotals(
                    record, alt_currency, ctx, include_igtf=True
                )
                foreign_currency_code = alt_currency.code_tfhka
            else:
                igtf_alt = 0.0
                amounts_foreign = {}
                taxes_subtotal_foreign = []
                foreign_currency_code = None

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
                payment_forms = self._prepare_payments(record, ctx)

                if payment_forms:
                    if len(payment_forms) > 5:
                        raise UserError(_("The maximum number of payment methods is 5. Please check your payment methods."))
                    if any(not method.get('forma') for method in payment_forms):
                        raise ValidationError(_("The payment method code is not configured in the journal."))
                    totals["formasPago"] = payment_forms

            if amounts_foreign:
                foreign_totals = {
                    "moneda": foreign_currency_code,
                    "tipoCambio": "{:.4f}".format(ctx["rate"]),
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

    def _prepare_tax_subtotals(self, invoice, currency, ctx, include_igtf=False):
        """Detalle de impuestos (``impuestosSubtotal``) expresado en ``currency``.

        Devuelve una lista; en 17.0 devolvía una tupla (base, alterna) y el
        llamador decidía cuál usar según tres criterios distintos. Ahora cada
        moneda se pide por separado.
        """
        invoice.ensure_one()
        keys = self._get_tax_totals_keys(invoice, currency)
        needs_conversion = keys is None
        if needs_conversion:
            keys = ("base_amount_currency", "tax_amount_currency", "total_amount_currency")
        base_key, tax_key, _total_key = keys

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
            base_amount = group.get(base_key, 0.0)
            tax_amount = group.get(tax_key, 0.0)
            if needs_conversion:
                base_amount = self._get_amount_in_currency(invoice, currency, ctx, base_amount)
                tax_amount = self._get_amount_in_currency(invoice, currency, ctx, tax_amount)
            tax_subtotals.append({
                "codigoTotalImp": TFHKA_TAX_CODE[group_name],
                "alicuotaImp": TFHKA_TAX_RATE[group_name],
                "baseImponibleImp": str(round(base_amount, 2)),
                "valorTotalImp": str(round(tax_amount, 2)),
            })

        if include_igtf:
            igtf = (invoice.tax_totals or {}).get("igtf") or {}
            if igtf.get("apply_igtf"):
                igtf_base, igtf_amount = self._get_igtf_block(invoice, currency, ctx)
                tax_subtotals.append({
                    "codigoTotalImp": "IGTF",
                    "alicuotaImp": TFHKA_TAX_RATE.get(igtf.get("name"), "3.0"),
                    "baseImponibleImp": str(round(igtf_base, 2)),
                    "valorTotalImp": str(round(igtf_amount, 2)),
                })

        return tax_subtotals

    def _prepare_detail_lines(self, invoice, ctx=None):
        ctx = ctx or self._get_currency_context(invoice)
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

                # Los montos de línea van en la moneda del documento. Se parte
                # de price_unit/price_subtotal (que están en la moneda de la
                # factura, o sea la de la tarifa) y se convierte con la tasa del
                # contexto; NO se usa foreign_price, que siempre convierte a
                # company.foreign_currency_id y rompería una tarifa en EUR con
                # la compañía en USD.
                document_currency = ctx["document_currency"]
                base_price = self._get_amount_in_currency(
                    record, document_currency, ctx, line.price_unit
                )
                base_subtotal = self._get_amount_in_currency(
                    record, document_currency, ctx, line.price_subtotal
                )

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

    def _prepare_payments(self, invoice, ctx=None):
        ctx = ctx or self._get_currency_context(invoice)
        try:
            payment_data = []
            for record in invoice:
                content_data = record.invoice_payments_widget.get("content", [])
                if content_data:
                    for item in content_data:
                        payment = self._get_payment(item.get('account_payment_id'))

                        if not payment:
                            continue

                        payment_info = self._build_payment_info(record, payment, ctx)
                        payment_data.append(payment_info)
                    return payment_data
            return False
        except Exception as e:
            _logger.error("Error processing payment methods: %s", e)
            return False

    def _get_payment(self, account_payment_id):
        return self.env['account.payment'].search([('id', '=', account_payment_id)])

    def _build_payment_info(self, invoice, payment, ctx=None):
        ctx = ctx or self._get_currency_context(invoice)
        payment_id = self.env['account.payment'].search([('id', '=', payment.id)])
        payment_currency = payment_id.currency_id or invoice.company_id.currency_id
        payment_method = payment_id.journal_id.payment_method_code if payment_id.journal_id.payment_method_code else False

        # La moneda del pago se reporta con su propio code_tfhka, igual que el
        # resto del payload: 17.0 mandaba aquí el nombre de la moneda de Odoo,
        # que no tiene por qué coincidir con el código de The Factory.
        self._check_currency_codes(payment_currency)
        currency_code = payment_currency.code_tfhka

        if payment_currency.name in VES_CURRENCY_NAMES:
            exchange_rate = None
        else:
            # Pago en divisa: se incluye el tipo de cambio del propio pago.
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
