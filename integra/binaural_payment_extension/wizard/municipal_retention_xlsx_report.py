from odoo import api, models, fields, _
from datetime import date
from dateutil.relativedelta import relativedelta
import xlsxwriter
from odoo.exceptions import MissingError, ValidationError
from io import BytesIO
import base64
import pandas
from collections import OrderedDict
from ..utils.utils_retention import get_current_date_format


class MunicipalRetentionXlsxReport(models.TransientModel):
    _name = "municipal.retention.xlsx.report"
    _description = "XLSX Report for municipal retentions"

    date_start = fields.Date(
        string="Fecha Inicio", required=True, default=date.today().replace(day=1)
    )
    date_end = fields.Date(
        string="Fecha fin",
        required=True,
        default=date.today().replace(day=1) + relativedelta(months=1, days=-1),
    )

    def print_xlsx(self):
        domain = self._get_municipal_retention_domain()
        retentions_count = self.env["account.retention"].search_count(domain)
        do_not_validate_missing_tax_authorities_name_per_company = self.env.context.get(
            "do_not_validate_missing_tax_authorities_name_per_company", False
        )

        if (
            not do_not_validate_missing_tax_authorities_name_per_company
            and not self.env.company.tax_authorities_name
        ):
            raise ValidationError(_("The company has no tax authorities name"))

        if not retentions_count:
            raise MissingError(
                _("There are no supplier municipal retentions for the given date range.")
            )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/get_xlsx_municipal_retentions_report?report_id=%s" % self.id,
            "target": "self",
        }

    def _xlsx_file(self, table, nombre):
        data2 = BytesIO()
        workbook = xlsxwriter.Workbook(data2, {"in_memory": True})
        merge_format = workbook.add_format(
            {
                "bold": 1,
                "align": "center",
                "border": 1,
                "fg_color": "#D3D3D3",
                "text_wrap": 1,
                "valign": "top",
            }
        )
        bold = workbook.add_format({"bold": 1})
        worksheet2 = workbook.add_worksheet(nombre)
        worksheet2.set_column("A:Z", 20)
        company = self.env.company
        tax_authorities_record = self._get_tax_authorities_record(company)
        if tax_authorities_record.tax_authorities_logo:
            tax_authorities_logo = BytesIO(base64.b64decode(tax_authorities_record.tax_authorities_logo))
            worksheet2.insert_image("A1", "image.png", {"image_data": tax_authorities_logo})
        worksheet2.write("C2", "RENDICIÓN INFORMATIVA MENSUAL DEL AGENTE DE RETENCIÓN", bold)
        if tax_authorities_record.tax_authorities_name:
            worksheet2.write("D4", tax_authorities_record.tax_authorities_name.upper(), bold)
        worksheet2.write("A8", "AGENTE DE RETENCIÓN:", bold)
        worksheet2.write("C8", company.name)
        worksheet2.write("A9", "NUMERO DE REGISTRO UNICO DE INFORMACION FISCAL:", bold)
        worksheet2.write("D9", company.partner_id.vat)
        worksheet2.write("A10", "DIRECCION FISCAL:", bold)
        worksheet2.write("B10", company.street)
        date = get_current_date_format(self.date_start)
        worksheet2.write("A11", "MES Y AÑO DECLARADO:", bold)
        worksheet2.write("C11", date)
        worksheet2.write(
            "A12",
            "FACTURA, ORDEN DE PAGO U OTRO INSTRUMENTO CONTABLE DONDE SE VERIFIQUE EL PAGO O ABONO EN CUENTA",
            bold,
        )

        worksheet2.set_row(13, 23, merge_format)
        worksheet2.set_row(13, 23, merge_format)
        columnas = list(table.columns.values)
        columns2 = [{"header": r} for r in columnas]
        currency_symbol = self.env.ref("base.VEF").symbol
        money_format = workbook.add_format({"num_format": '#,##0.00 "' + currency_symbol + '"'})
        # control_format = workbook.add_format({'align': 'center'})
        porcent_format = workbook.add_format({"num_format": "0.0 %"})
        # columns2[0].update({'format': control_format})
        columns2[10].update({"format": porcent_format})
        # columns2[4].update({'format': money_format})
        columns2[9].update({"format": money_format})
        columns2[11].update({"format": money_format})

        data = table.values.tolist()
        col3 = len(columns2) - 1
        col2 = len(data) + 14
        cells = xlsxwriter.utility.xl_range(13, 0, col2, col3)

        total_retained = 0
        for col in data:
            total_retained = col[11] + total_retained

        total = 0
        for col in data:
            total = col[9] + total
        worksheet2.hide_gridlines(2)
        worksheet2.add_table(
            cells, {"data": data, "total_row": True, "columns": columns2, "autofilter": False}
        )
        worksheet2.write("L" + str(col2 + 1), total_retained, money_format)
        worksheet2.write("J" + str(col2 + 1), total, money_format)
        worksheet2.write(
            "A" + str(col2 + 4),
            "Declaro, bajo juramento la veracidad de los datos contenidos en el presente formulario, quedando sometidos a las sanciones establecidas por la ley en   caso que determiné la falsedad de algún dato suministrado.",
            bold,
        )
        worksheet2.write(
            "A" + str(col2 + 5),
            "Agente de retención Responsable de la Declaración ____________________________________",
            bold,
        )
        worksheet2.write(
            "A" + str(col2 + 6), "Cédula de Identidad ___________________________________", bold
        )
        worksheet2.write(
            "A" + str(col2 + 7), "Cargo: ______________________________________________", bold
        )
        worksheet2.write("F" + str(col2 + 9), "Firma y sello", bold)
        workbook.close()
        data2 = data2.getvalue()
        return data2

    def _get_tax_authorities_record(self, company):
        return company

    def _get_xlsx_municipal_retention_report(self):
        domain = self._get_municipal_retention_domain()
        retentions = self.env["account.retention"].search(domain, order="date_accounting asc")

        lista = []
        cols = OrderedDict(
            [
                ("Nº", ""),
                ("Tipo de Instrumento", ""),
                ("Nº de Instrumento", ""),
                ("Fecha de Emision", ""),
                ("Contribuyente", ""),
                ("R.I.F.", ""),
                ("Domicilio Fiscal", ""),
                ("Descripcion del Documento", ""),
                ("Actividad Económica", ""),
                ("Monto Bruto", 0.00),
                ("Alícuota %", ""),
                ("Monto Retenido", 0.00),
            ]
        )
        base_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        numero = 1
        for retention in retentions:
            retention_lines = self._get_filtered_retention_lines(retention.retention_line_ids)
            for retention_line in retention_lines:
                invoice_amount = 0
                retention_amount = 0

                if base_currency == usd:
                    invoice_amount = retention_line.foreign_invoice_amount
                    retention_amount = retention_line.foreign_retention_amount
                else:
                    invoice_amount = retention_line.invoice_amount
                    retention_amount = retention_line.retention_amount

                invoice_type = ""

                if retention_line.move_id.move_type == ["in_invoice", "out_invoice"]:
                    invoice_type = "F"
                elif retention_line.move_id.move_type == ["in_refund", "out_refund"]:
                    invoice_type = "NC"

                rows = OrderedDict()
                rows.update(cols)
                rows["Nº"] = numero
                rows["Tipo de Instrumento"] = invoice_type
                rows["Monto Bruto"] = invoice_amount
                rows["Nº de Instrumento"] = retention.name
                rows["Fecha de Emision"] = retention.date_accounting.strftime("%d-%m-%Y")
                rows["Contribuyente"] = retention.partner_id.name
                rows["R.I.F."] = str(retention.partner_id.prefix_vat) + str(
                    retention.partner_id.vat
                )
                rows["Domicilio Fiscal"] = retention.partner_id.street
                rows["Descripcion del Documento"] = retention_line.move_id.name
                rows["Actividad Económica"] = retention_line.economic_activity_id.name
                rows["Monto Bruto"] = invoice_amount
                rows["Alícuota %"] = retention_line.aliquot / 100
                rows["Monto Retenido"] = retention_amount

                lista.append(rows)
                numero += 1
        table = pandas.DataFrame(lista)
        return table.fillna(0)

    def _get_filtered_retention_lines(self, lines):
        return lines

    def _get_municipal_retention_domain(self):
        return [
            ("date_accounting", ">=", self.date_start),
            ("date_accounting", "<=", self.date_end),
            ("state", "=", "emitted"),
            ("type", "=", "in_invoice"),
            ("type_retention", "=", "municipal"),
        ]
