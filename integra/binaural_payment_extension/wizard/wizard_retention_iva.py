from dateutil.relativedelta import relativedelta
from odoo import fields, models, _
from odoo.exceptions import UserError
from datetime import date


class TxtWizard(models.TransientModel):
    _name = "wizard.retention.iva"
    _description = "File IVA taxes with the SENIAT"

    date_start = fields.Date(default=date.today().replace(day=1))
    date_end = fields.Date(default=date.today().replace(day=1) + relativedelta(months=1, days=-1))

    def generate_txt(self):
        company_id = self.env.company.id
        if not (self.date_start and self.date_end):
            raise UserError(_("You must enter a start and end date"))
        retention_count = self.env["account.retention"].search_count(
            [
                ("date", ">=", self.date_start),
                ("date", "<=", self.date_end),
                ("state", "=", "emitted"),
                ("type_retention", "=", "iva"),
                ("type", "=", "in_invoice"),
                ("company_id", "=", company_id),
            ]
        )
        if retention_count == 0:
            raise UserError(_("No retentions found for the selected period"))

        url = "/web/binary/download_retention_iva_txt?&date_start=%s&date_end=%s&company_id=%s" % (
            self.date_start,
            self.date_end,
            str(company_id),
        )
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _retention_iva(self, retentions):
        document_types = {
            "in_invoice": "01",
            "in_debit": "02",
            "in_refund": "03",
        }

        data = []
        for line in retentions.mapped("retention_line_ids"):
            line_data = {}
            line_data["RIF del agente de retención"] = line.retention_id.company_id.partner_id.vat
            line_data["Período impositivo"] = line.retention_id.date.strftime("%Y%m")
            line_data["Fecha de factura"] = line.move_id.date.strftime("%Y-%m-%d")
            line_data["Tipo de operación"] = "C"
            line_data["Tipo de documento"] = document_types[line.move_id.move_type]
            line_data["RIF de proveedor"] = (
                line.move_id.partner_id.prefix_vat + line.move_id.partner_id.vat
            )
            line_data["Número de documento"] = line.move_id.name
            line_data["Número de control"] = line.move_id.correlative
            line_data["Número del documento afectado"] = line.move_id.reversed_entry_id.name or "0"
            line_data["Número de comprobante de retención"] = (
                int(line.retention_id.number) if line.retention_id.number else 0
            )
            line_data["Alícuota"] = line.aliquot
            if not line.retention_id.base_currency_is_vef:
                exempt_amount = sum(
                    line.move_id.invoice_line_ids.filtered(lambda l: l.tax_ids.amount == 0).mapped(
                        "foreign_subtotal"
                    )
                )

                line_data["Monto total del documento"] = (
                    line.foreign_invoice_amount + line.foreign_iva_amount + exempt_amount
                )
                line_data["Base imponible"] = line.foreign_invoice_amount
                line_data["Monto del Iva Retenido"] = line.foreign_retention_amount
                line_data["Monto exento del IVA"] = exempt_amount
            else:
                exempt_amount = sum(
                    line.move_id.invoice_line_ids.filtered(lambda l: l.tax_ids.amount == 0).mapped(
                        "price_subtotal"
                    )
                )
                line_data["Monto total del documento"] = (
                    line.invoice_amount + line.iva_amount + exempt_amount
                )
                line_data["Base imponible"] = line.invoice_amount
                line_data["Monto del Iva Retenido"] = line.retention_amount
                line_data["Monto exento del IVA"] = exempt_amount
            line_data["Número de Expediente"] = "0"
            data.append(line_data)
        return data
