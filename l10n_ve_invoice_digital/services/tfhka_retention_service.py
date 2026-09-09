import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .tfhka_document_service import EXEMPT_TAX_GROUPS

_logger = logging.getLogger(__name__)

class TfhkaRetentionService(models.AbstractModel):
    """Arma y envía los comprobantes de retención (IVA 05 / ISLR 06) a TFHKA.

    Paralelo a ``unidigital.retention.service``. El transporte HTTP lo hace
    ``tfhka.api.client``, al que la compañía se pasa explícita. Extensible vía
    el hook ``_prepare_extra_retention_values``.
    """

    _name = "tfhka.retention.service"
    _inherit = "tfhka.service.base"
    _description = "TFHKA Retention Service"

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def send_retention(self, retention):
        retention.ensure_one()
        if not retention.company_id.invoice_digital_tfhka:
            return
        if retention.is_digitalized:
            raise UserError(_("The document has already been digitalized."))
        document_type = retention.env.context.get('document_type')
        company = retention.company_id
        client = self.env["tfhka.api.client"]
        client.query_numbering(company)
        document_number = client.get_last_document_number(company, document_type)

        document_number_str = str(document_number)
        if len(document_number_str) > 6:
            document_number = int(document_number_str[6:]) + 1
        else:
            document_number = int(document_number_str) + 1

        current_number = int(retention.number[6:])
        validation_sequence = retention.env.context.get('account_retention_alert', False)

        if document_number != current_number and not validation_sequence and retention.company_id.sequence_validation_tfhka:
            message = _("The document sequence in Odoo (%(odoo_seq)s) does not match the sequence in The Factory (%(factory_seq)s). Do you want to continue anyway?") % {"odoo_seq": current_number, "factory_seq": document_number}
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.retention.alert.wizard',
                'view_mode': 'form',
                'view_id': retention.env.ref('l10n_ve_invoice_digital.account_retention_alert_wizard').id,
                'target': 'new',
                'context': {
                    'default_move_id': retention.id,
                    'default_message': message,
                }
            }

        document_number = str(retention.number)

        return self.generate_document_data(retention, document_number, document_type, validation_sequence)

    def annul_retention(self, retention, reason):
        """Anula la retención digitalizada en TFHKA (endpoint /Anular).

        Envía serie/tipoDocumento/numeroDocumento + motivo y fecha/hora
        automáticas. Marca ``annulled_tfhka`` al confirmar.
        """
        retention.ensure_one()
        company = retention.company_id
        if not retention.is_digitalized:
            raise UserError(_("The retention has not been digitalized; it cannot be annulled."))
        if retention.annulled_tfhka:
            raise UserError(_("The retention has already been annulled in The Factory HKA."))

        document_type = "05" if retention.type_retention == "iva" else "06"
        document_number = retention.document_number_tfhka or str(retention.number)
        now_local = self._get_emission_datetime(retention)

        payload = {
            "serie": "",
            "tipoDocumento": document_type,
            "numeroDocumento": document_number,
            "motivoAnulacion": reason,
            "fechaAnulacion": now_local.strftime("%d/%m/%Y"),
            "horaAnulacion": now_local.strftime("%I:%M:%S %p").lower(),
        }

        self.env["tfhka.api.client"].annul(company, payload)
        retention.write({"annulled_tfhka": True})
        retention.message_post(
            body=_("Retention annulled in The Factory HKA. Reason: %s", reason),
            message_type='comment',
        )
        return True

    def generate_document_data(self, retention, document_number, document_type, validation_sequence):
        document_identification = self._prepare_identification(retention, document_type, document_number)
        subject_retention = self._get_fiscal_party(retention)
        total_retention = self._prepare_totals(retention, document_type)
        retention_details = self._prepare_detail_lines(retention, document_type)

        payload = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": document_identification,
                    "sujetoRetenido": subject_retention,
                    "totalesRetencion": total_retention
                },
                "detallesRetencion": retention_details,
            }
        }
        payload["documentoElectronico"].update(self._prepare_extra_retention_values(retention))

        response = self.env["tfhka.api.client"].emit(retention.company_id, payload)

        if response:
            retention.is_digitalized = True
            retention.control_number_tfhka = response.get("resultado").get("numeroControl")
            retention.document_number_tfhka = str(document_number)
            emission_date = fields.Datetime.now().strftime("%d/%m/%Y")
            if validation_sequence:
                retention.message_post(
                    body=_("Warning accepted: The difference in sequence between Odoo and The Factory is acknowledged and accepted."),
                    message_type='comment',
                )
            retention.message_post(
                body=_("Document successfully digitized on %(date)s") % {"date": emission_date},
                message_type='comment',
            )

            return

    def _prepare_extra_retention_values(self, retention):
        """Hook de extensión: valores extra del payload. Por defecto vacío."""
        return {}

    # ------------------------------------------------------------------
    # Secciones del payload
    # ------------------------------------------------------------------

    def _prepare_identification(self, retention, document_type, document_number):
        for record in retention:
            now_local = self._get_emission_datetime(record)
            emission_time = now_local.strftime("%I:%M:%S %p").lower()
            emission_date = now_local.strftime("%d/%m/%Y")
            affected_invoice_number = ""

            for line in record.retention_line_ids:
                prefix = ""
                if line.move_id.debit_origin_id:
                    affected_invoice_number = str(line.move_id.debit_origin_id.sequence_number)

                if line.move_id.reversed_entry_id:
                    affected_invoice_number = str(line.move_id.reversed_entry_id.sequence_number)

            return {
                "tipoDocumento": document_type,
                "numeroDocumento": document_number,
                "numeroFacturaAfectada": affected_invoice_number,
                "fechaEmision": emission_date,
                "horaEmision": emission_time,
                "serie": "",
                "sucursal": "",
                "tipoDeVenta": "Interna",
                "moneda": record.company_id.currency_id.name,
            }

    def _prepare_totals(self, retention, document_type):
        retention_data = {}

        for record in retention:

            if record.base_currency_is_vef:
                total_invoice = str(round(abs(record.total_invoice_amount), 2))
                total_iva = str(round(abs(record.total_iva_amount), 2))
                total_retention = str(round(abs(record.total_retention_amount), 2))

            else:
                total_invoice = str(round(abs(record.foreign_total_invoice_amount), 2))
                total_iva = str(round(abs(record.foreign_total_iva_amount), 2))
                total_retention = str(round(abs(record.foreign_total_retention_amount), 2))

            retention_data = {
                "totalBaseImponible": total_invoice,
                "numeroCompRetencion": record.number,
                "fechaEmisionCR": record.date.strftime("%d/%m/%Y"),
                "tipoComprobante": "" if record.total_iva_amount or record.foreign_total_iva_amount else "1",
            }
            if document_type == "05":
                retention_data["totalRetenido"] = total_retention
                retention_data["totalIVA"] = total_iva
            else:
                retention_data["TotalISRL"] = total_retention

            return retention_data

    def _get_exempt_amount(self, move, base_currency_is_vef):
        """Monto exento (Exento/IVA 0%) de la factura afectada, en la misma
        moneda que el resto de la linea.

        O19 sustituyó ``groups_by_subtotal`` / ``groups_by_foreign_subtotal`` por
        una única lista ``subtotals``, donde cada cubeta lleva sus ``tax_groups``
        con las dos monedas en claves distintas. No se asume el nombre de la
        cubeta (en ventas "Subtotal", en compras "Untaxed Amount").
        """
        base_key = "base_amount_currency" if base_currency_is_vef else "base_amount_foreign_currency"
        return sum(
            group.get(base_key, 0.0)
            for subtotal in (move.tax_totals or {}).get("subtotals", [])
            for group in subtotal.get("tax_groups", [])
            if group.get("group_name") in EXEMPT_TAX_GROUPS
        )

    def _prepare_detail_lines(self, retention, document_type):
        retention_details = []
        type_document = {
            "in_invoice": "01",
            "in_refund": "02",
        }

        counter = 1
        for record in retention:
            for line in record.retention_line_ids:
                line_document_type = type_document.get(line.move_id.move_type, "03") if not line.move_id.debit_origin_id else "03"
                series = line.move_id.name
                document_series_ret = ''.join([c for c in series if c.isalpha()])
                document_number_ret = str(''.join([c for c in series if c.isdigit()]))

                if record.base_currency_is_vef:
                    invoice_total = str(round(line.invoice_total, 2))
                    invoice_amount = str(round(line.invoice_amount, 2))
                    retention_amount = str(round(line.retention_amount, 2))
                    iva_amount = str(round(line.iva_amount, 2))

                else:
                    invoice_total = str(round(line.foreign_invoice_total, 2))
                    invoice_amount = str(round(line.foreign_invoice_amount, 2))
                    retention_amount = str(round(line.foreign_retention_amount, 2))
                    iva_amount = str(round(line.foreign_iva_amount, 2))

                retention_data = {
                    "numeroLinea": str(counter),
                    "fechaDocumento": line.move_id.invoice_date.strftime("%d/%m/%Y"),
                    "tipoDocumento": line_document_type,
                    "serieDocumento": document_series_ret,
                    "numeroDocumento": document_number_ret,
                    "numeroControl": line.move_id.correlative,
                    "montoTotal": invoice_total,
                    "baseImponible": invoice_amount,
                    "moneda": record.company_id.currency_id.name,
                    "retenido": retention_amount,
                }

                if document_type == "05":
                    retention_data["montoIVA"] = iva_amount
                    retention_data["porcentaje"] = str(round(line.aliquot, 2))
                    retention_data["retenidoIVA"] = str(round(line.related_percentage_tax_base, 2))
                    retention_data["montoExento"] = str(round(
                        self._get_exempt_amount(line.move_id, record.base_currency_is_vef), 2
                    ))

                if document_type == "06":
                    code = line.code
                    if code:
                        retention_data["CodigoConcepto"] = code.zfill(3)

                    retention_data["porcentaje"] = str(round(line.related_percentage_fees, 2))

                retention_details.append(retention_data)
                counter += 1

        return retention_details
