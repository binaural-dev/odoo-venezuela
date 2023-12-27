from odoo import models, tools
from datetime import date
import xlsxwriter
from io import BytesIO
import base64
import pandas
from collections import OrderedDict


class MunicipalRetentionXlsx(models.AbstractModel):
    _name = "municipal.retention.xlsx"

    def xlsx_file(self, tabla, nombre, retention_id):
        company = self.env.company
        currency_symbol = self.env.ref("base.VEF").symbol
        retention = self.env["account.retention"].browse(retention_id)
        data2 = BytesIO()
        workbook = xlsxwriter.Workbook(data2, {"in_memory": True})
        merge_format = workbook.add_format(
            {
                "bold": 1,
                "align": "center",
                "border": 1,
                "valign": "vcenter",
                "fg_color": "#D3D3D3",
                "text_wrap": 1,
                "valign": "top",
            }
        )
        bold = workbook.add_format({"bold": 1})
        boldWithBorder = workbook.add_format({"bold": 1, "border": 1})
        boldWithBorderJustify = workbook.add_format(
            {"bold": 1, "border": 1, "text_wrap": True, "valign": "top", "align": "justify"}
        )
        datos = tabla
        worksheet2 = workbook.add_worksheet(nombre)
        worksheet2.set_column("A:Z", 20)
        tax_authorities_record = self._get_tax_authorities_record(company, retention_id)
        if tax_authorities_record.tax_authorities_logo:
            tax_authorities_logo = BytesIO(
                base64.b64decode(tax_authorities_record.tax_authorities_logo)
            )
            worksheet2.insert_image("A2", "image.png", {"image_data": tax_authorities_logo})
        tax_authorities_name = tax_authorities_record.tax_authorities_name or ""

        worksheet2.write(
            "C2",
            "A fin de cumplir con el art. 136 de la Ordenanza de Impuestos a las Actividades Economicas, Comercios, Servicios",
            bold,
        )
        worksheet2.write(
            "C3",
            "o de indole similar y el Decreto A-05-01-2016   Art. 8 Reglamento de Retenciones sobre Retenciones Actividades Econòmicas",
            bold,
        )
        worksheet2.write(
            "C5",
            f"COMPROBANTE DE RETENCION IMPUESTO ACTIVIDADES ECONOMICAS {tax_authorities_name.upper()}",
            bold,
        )
        worksheet2.write("D7", "AGENTE DE RETENCIÓN", bold)
        worksheet2.write("G7", "COMPROBANTE:", boldWithBorder)
        worksheet2.write("G8", retention.name, boldWithBorder)
        worksheet2.write_rich_string("A11", bold, "RAZÓN SOCIAL :", str(company.name))
        worksheet2.write_rich_string(
            "A12",
            bold,
            "NUMERO DE REGISTRO ÚNICO DE INFORMACIÓN FISCAL: ",
            str(company.partner_id.vat),
        )
        worksheet2.write_rich_string(
            "E12",
            bold,
            "NUMERO DE LICENCIA DE ACTIVIDADES ECONOMICAS: ",
            str(tax_authorities_record.economic_activity_number),
        )
        worksheet2.write_rich_string("A13", bold, "DIRECCIÓN FISCAL: ", company.street)
        worksheet2.write("G14", "FECHA DE EMISIÓN O TRANSACCION", boldWithBorderJustify)
        worksheet2.write(
            "G15", retention.date_accounting.strftime("%d-%m-%Y"), boldWithBorderJustify
        )
        worksheet2.write("H14", "FECHA DE ENTREGA", boldWithBorderJustify)
        today = date.today()
        worksheet2.write("H15", today.strftime("%d-%m-%Y"), boldWithBorderJustify)
        worksheet2.write("D15", "CONTRIBUYENTE", bold)
        worksheet2.write_rich_string("A16", bold, "RAZÓN SOCIAL: ", str(retention.partner_id.name))
        worksheet2.write_rich_string(
            "A17",
            bold,
            "NUMERO DE REGISTRO ÚNICO DE INFORMACIÓN FISCAL: ",
            str(retention.partner_id.prefix_vat) + str(retention.partner_id.vat),
        )
        worksheet2.write("G17", "Periodo Fiscal", boldWithBorder)
        worksheet2.write("G18", "Año:", boldWithBorder)
        month = retention.date_accounting.month
        year = retention.date_accounting.year
        worksheet2.write("G19", year, boldWithBorder)
        worksheet2.write("H18", "Mes:", boldWithBorder)
        worksheet2.write("H19", month, boldWithBorder)
        worksheet2.write_rich_string(
            "A18", bold, "DIRECCIÓN FISCAL: ", str(retention.partner_id.street)
        )
        worksheet2.write("D22", "DATOS DE LA TRANSACCIÓN", bold)
        worksheet2.set_row(24, 23, merge_format)
        worksheet2.set_row(24, 23, merge_format)
        columnas = list(datos.columns.values)
        columns2 = [{"header": r} for r in columnas]
        money_format = workbook.add_format({"num_format": '#,##0.00 "' + currency_symbol + '"'})
        control_format = workbook.add_format({"align": "center"})
        porcent_format = workbook.add_format({"num_format": "0.0 %"})
        columns2[0].update({"format": control_format})
        columns2[5].update({"format": porcent_format})
        columns2[4].update({"format": money_format})
        columns2[7].update({"format": money_format})
        columns2[8].update({"format": money_format})

        data = datos.values.tolist()
        col3 = len(columns2) - 1
        col2 = len(data) + 25
        total_retained = 0
        for col in data:
            total_retained = col[8] + total_retained
        cells = xlsxwriter.utility.xl_range(24, 0, col2, col3)
        worksheet2.hide_gridlines(2)
        worksheet2.add_table(
            cells, {"data": data, "total_row": True, "columns": columns2, "autofilter": False}
        )
        worksheet2.write("I" + str(col2 + 1), total_retained, money_format)
        boldWithBorderTop = workbook.add_format({"bold": 1, "top": 1})

        worksheet2.write(
            "B" + str(col2 + 12), "\t\tFirma del Agente de Retención", boldWithBorderTop
        )
        worksheet2.write("C" + str(col2 + 12), "", boldWithBorderTop)

        worksheet2.write("F" + str(col2 + 12), "Firma del Beneficiario", boldWithBorderTop)

        signature = self.env["signature.config"].search(
            [("active", "=", True)], limit=1, order="id asc"
        )

        if any(signature) and signature.signature:
            logo = tools.image_process(base64.b64decode(signature.signature), (200, 200))
            image_signature = BytesIO(logo)
            worksheet2.insert_image(
                "F" + str(col2 + 5), "image.png", {"image_data": image_signature}
            )

        workbook.close()
        data2 = data2.getvalue()
        return data2

    def get_xlsx_municipal_retention(self, retention_id):
        retention = self.env["account.retention"].browse(retention_id)

        lista = []
        cols = OrderedDict(
            [
                ("Nº de la Op", ""),
                ("Fecha de Factura", ""),
                ("Nº de Factura", ""),
                ("Nº de Control", ""),
                ("Base Imponible", 0.00),
                ("Alícuota %", 0.00),
                ("Actividad Económica", 0.00),
                ("Impuesto Municipal Retenido", 0.00),
                ("IMPUESTO RETENIDO", 0.00),
            ]
        )
        base_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD")

        for index, retention_line in enumerate(retention.retention_line_ids):
            invoice_amount = 0
            retention_amount = 0

            if base_currency == usd:
                invoice_amount = retention_line.foreign_invoice_amount
                retention_amount = retention_line.foreign_retention_amount
            else:
                invoice_amount = retention_line.invoice_amount
                retention_amount = retention_line.retention_amount

            rows = OrderedDict()
            rows.update(cols)
            rows["Nº de la Op"] = index + 1
            rows["Fecha de Factura"] = retention_line.move_id.invoice_date.strftime("%d-%m-%Y")
            rows["Nº de Factura"] = retention_line.move_id.name
            rows["Nº de Control"] = retention_line.move_id.correlative
            rows["Base Imponible"] = invoice_amount
            rows["Alícuota %"] = retention_line.aliquot / 100
            rows["Actividad Económica"] = retention_line.economic_activity_id.name
            rows["Impuesto Municipal Retenido"] = retention_amount
            rows["IMPUESTO RETENIDO"] = retention_amount

            lista.append(rows)

        tabla = pandas.DataFrame(lista)
        return tabla.fillna(0)

    def _get_tax_authorities_record(self, company, retention_id):
        return company
