import re

from odoo import _, fields, models
from odoo.exceptions import UserError

DOCUMENT_TYPE = "04"


class TfhkaDispatchGuideService(models.AbstractModel):
    """Arma y envía las guías de despacho a TFHKA.

    Paralelo a ``tfhka.document.service``/``tfhka.retention.service``. El
    transporte HTTP lo hace ``tfhka.api.client``, al que la compañía se pasa
    explícita. Reutiliza de ``tfhka.service.base`` la fecha/hora de emisión y
    el armado del nodo ``comprador`` a través de sus puntos de extensión
    (``_get_party_source``/``_get_party_address``).
    """

    _name = "tfhka.dispatch.guide.service"
    _inherit = "tfhka.service.base"
    _description = "TFHKA Dispatch Guide Service"

    # ------------------------------------------------------------------
    # Puntos de extensión de tfhka.service.base
    # ------------------------------------------------------------------

    def _get_party_source(self, picking):
        picking.ensure_one()
        return picking.partner_id.parent_id or picking.partner_id

    def _get_party_address(self, partner):
        return partner.contact_address_complete or "no definida"

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def send_document(self, picking):
        picking.ensure_one()
        if picking.is_digitalized:
            raise UserError(_("The document has already been digitalized."))

        client = self.env["tfhka.api.client"]
        company = picking.company_id

        client.query_numbering(company)
        document_number = client.get_last_document_number(company, DOCUMENT_TYPE)
        document_number = document_number + 1

        sequence = self.env["ir.sequence"].sudo()
        current_number = sequence.search(
            [("code", "=", "guide.number"), ("company_id", "=", company.id)]
        ).number_next_actual

        if document_number != current_number and company.sequence_validation_tfhka:
            raise UserError(_(
                "The document sequence in Odoo (%(odoo_seq)s) does not match the sequence "
                "in The Factory (%(factory_seq)s). Please check your numbering settings.",
                odoo_seq=current_number, factory_seq=document_number,
            ))

        document_number = str(document_number)

        return self.generate_document_data(picking, document_number, DOCUMENT_TYPE)

    def generate_document_data(self, picking, document_number, document_type):
        document_identification = self._prepare_identification(picking, document_type, document_number)
        buyer = self._get_fiscal_party(picking)
        details_items = self._prepare_detail_lines(picking)
        dispatch_guide = self._prepare_dispatch_guide(picking)
        additional_information = self._prepare_additional_information(picking)

        payload = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": document_identification,
                    "comprador": buyer,
                },
                "detallesItems": details_items,
                "guiaDespacho": dispatch_guide,
            }
        }

        if additional_information:
            payload["documentoElectronico"]["infoAdicional"] = additional_information

        payload["documentoElectronico"].update(self._prepare_extra_payload_values(picking))

        response = self.env["tfhka.api.client"].emit(picking.company_id, payload)

        if response:
            self._register_success(picking, response)

    def _register_success(self, picking, response):
        picking.control_number_tfhka = response.get("resultado").get("numeroControl")
        picking.is_digitalized = True
        picking._set_guide_number()
        emission_date = fields.Datetime.now().strftime("%d/%m/%Y")
        picking.message_post(
            body=_("Document successfully digitized on %(date)s", date=emission_date),
            message_type='comment',
        )

    def _prepare_extra_payload_values(self, picking):
        """Hook de extensión: valores extra del payload. Por defecto vacío."""
        return {}

    # ------------------------------------------------------------------
    # Secciones del payload
    # ------------------------------------------------------------------

    def _prepare_identification(self, picking, document_type, document_number):
        for record in picking:
            now_local = self._get_emission_datetime(record)
            emission_time = now_local.strftime("%I:%M:%S %p").lower()
            emission_date = now_local.strftime("%d/%m/%Y")
            due_date = record.date_deadline.strftime("%d/%m/%Y") if record.date_deadline else emission_date

            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "fechaEmision": emission_date,
                "fechaVencimiento": due_date,
                "horaEmision": emission_time,
                "tipoDePago": self._get_payment_type(record),
                "serie": "",
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": "VEF",
                "transaccionId": "",
                "urlPdf": ""
            }

    def _get_payment_type(self, picking):
        for record in picking.sale_id:
            if record.payment_term_id.line_ids.nb_days > 0:
                return "Crédito"
            else:
                return "Inmediato"

    def _prepare_detail_lines(self, picking):
        item_details = []
        line_number = 1
        for record in picking:
            if record.sale_id and record.transfer_reason_id.code == "sale":
                for move_line in record.move_ids_without_package:
                    sale_line = move_line.sale_line_id

                    tax_mapping = {
                        0.0: "E",
                        8.0: "R",
                        16.0: "G",
                        31.0: "A",
                    }
                    taxes = sale_line.tax_id.filtered(lambda t: t.amount)
                    tax_rate = taxes[0].amount if taxes else 0.0

                    if record.sale_id.currency_id.name == "VEF":
                        unit_price = round(sale_line.price_unit, 2)
                    else:
                        unit_price = round(sale_line.foreign_price, 2)

                    item_price = round(unit_price * move_line.quantity, 2)
                    vat = round(item_price * sale_line.tax_id.amount / 100, 2)
                    total_item_value = round(item_price + vat, 2)

                    item_details.append({
                        "numeroLinea": str(line_number),
                        "codigoPLU": sale_line.product_id.barcode or sale_line.product_id.default_code or "",
                        "indicadorBienoServicio": "2" if sale_line.product_id.type == 'service' else "1",
                        "descripcion": sale_line.product_id.name,
                        "cantidad": str(move_line.quantity),
                        "precioUnitario": str(unit_price),
                        "precioItem": str(item_price),
                        "codigoImpuesto": tax_mapping[tax_rate],
                        "tasaIVA": str(round(sale_line.tax_id.amount, 2)),
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

    def _prepare_dispatch_guide(self, picking):
        for record in picking:
            product_origin_set = set()
            product_origin = ""

            for line in record.sale_id.order_line:
                if line.product_id.country_of_origin.name:
                    if line.product_id.country_of_origin.name == record.company_id.country_id.name:
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

    def _prepare_additional_information(self, picking):
        additional_information = []
        for record in picking:
            if record.partner_id:
                additional_information.append({
                    "campo": "direccionEntrega",
                    "valor": record.partner_id.contact_address_complete or "no definida",
                })
        return additional_information
