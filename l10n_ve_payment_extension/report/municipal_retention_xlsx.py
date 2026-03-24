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
        # --- 1. DATOS INICIALES Y WORKBOOK ---
        company = self.env.company
        retention = self.env["account.retention"].browse(retention_id)
        currency_symbol = self.env.ref("base.VEF").symbol
        
        data_io = BytesIO()
        workbook = xlsxwriter.Workbook(data_io, {"in_memory": True})
        worksheet = workbook.add_worksheet(nombre)
        worksheet.set_column("A:Z", 20)
        worksheet.hide_gridlines(2)

        # --- 2. DEFINICIÓN DE FORMATOS ---
        fmt_merge_header = workbook.add_format({
            "bold": 1, "align": "center", "border": 1, "valign": "top",
            "fg_color": "#7C94D4", "center_across": True, "text_wrap": True,
        })
        fmt_bold = workbook.add_format({"bold": 1})
        fmt_bold_border = workbook.add_format({"bold": 1, "border": 1, "align": "center"})
        fmt_bold_justify = workbook.add_format({
            "bold": 1, "border": 1, "text_wrap": 1, "valign": "top", "align": "center"
        })
        fmt_money = workbook.add_format({"num_format": f'#,##0.00 "{currency_symbol}"',"align": "center","valign": "center"})
        fmt_center = workbook.add_format({"align": "center","valign": "center"})
        fmt_percent = workbook.add_format({"num_format": "0.00 %","align": "center","valign": "center"})
        fmt_signature_line = workbook.add_format({"bold": 1, "top": 1})
      

        # --- 3. ENCABEZADO Y LOGO ---
        tax_auth = self._get_tax_authorities_record(company, retention_id)
        if tax_auth.tax_authorities_logo:
            logo_data = BytesIO(base64.b64decode(tax_auth.tax_authorities_logo))
            worksheet.insert_image("A2", "logo.png", {"image_data": logo_data})

        text1 = company.text_header_1_municipal_retention or ""
        text2 = company.text_header_2_municipal_retention or ""
        tax_name = (tax_auth.tax_authorities_name or "").upper()
        worksheet.write("B2", text1, fmt_bold)
        worksheet.write("C3", text2, fmt_bold)
        worksheet.write("C5", f"COMPROBANTE DE RETENCION IMPUESTO ACTIVIDADES ECONOMICAS {tax_name}", fmt_bold)

        # --- 4. SECCIÓN AGENTE DE RETENCIÓN ---
        worksheet.write("D7", "AGENTE DE RETENCIÓN", fmt_bold)
        worksheet.merge_range("G7:H7", "COMPROBANTE", fmt_bold_border)
        worksheet.merge_range("G8:H8", retention.name, fmt_bold_border)
        
        worksheet.write_rich_string("A11", fmt_bold, "RAZÓN SOCIAL :", str(company.name))
        worksheet.write_rich_string("A12", fmt_bold, "NUMERO DE REGISTRO ÚNICO DE INFORMACIÓN FISCAL: ", str(company.partner_id.vat))
        worksheet.write_rich_string("E11", fmt_bold, "NUMERO DE LICENCIA DE ACTIVIDADES ECONOMICAS: ", str(tax_auth.economic_activity_number))
        worksheet.write_rich_string("A13", fmt_bold, "DIRECCIÓN FISCAL: ", company.street or "")

        # Fechas
        

        if not retention.company_id.hide_issue_date_of_municipal_withholding_receipt:
            worksheet.write("G14", "FECHA DE EMISIÓN O TRANSACCION", fmt_bold_justify)
            worksheet.write("G15", retention.date_accounting.strftime("%d-%m-%Y"), fmt_bold_justify)
       
            worksheet.write("H14", "FECHA DE ENTREGA", fmt_bold_justify)
            worksheet.write("H15", retention.date_emision.strftime("%d-%m-%Y"), fmt_bold_justify)

        else:
            worksheet.merge_range("G14:H14", "FECHA DE EMISIÓN O TRANSACCION", fmt_bold_justify)
            worksheet.merge_range("G15:H15", retention.date_accounting.strftime("%d-%m-%Y"), fmt_bold_justify)
            

        # --- 5. SECCIÓN CONTRIBUYENTE ---
        worksheet.write("D15", "CONTRIBUYENTE", fmt_bold)
        worksheet.write_rich_string("A16", fmt_bold, "RAZÓN SOCIAL: ", str(retention.partner_id.name))
        worksheet.write_rich_string("A17", fmt_bold, "NUMERO DE REGISTRO ÚNICO DE INFORMACIÓN FISCAL: ", f"{retention.partner_id.prefix_vat or ''}{retention.partner_id.vat or ''}")
        
        # Periodo Fiscal
        worksheet.write("G17", "Periodo Fiscal", fmt_bold_border)
        worksheet.merge_range("G17:H17", "Periodo FiscaL", fmt_bold_border)
        worksheet.write("G18", "Año:", fmt_bold_border)
        worksheet.write("H18", "Mes:", fmt_bold_border)
        worksheet.write("G19", retention.date_accounting.year, fmt_bold_border)
        worksheet.write("H19", retention.date_accounting.month, fmt_bold_border)
        worksheet.write_rich_string("A18", fmt_bold, "DIRECCIÓN FISCAL: ", str(retention.partner_id.street or ""))

        # --- 6. TABLA DE TRANSACCIONES ---
        worksheet.write("D22", "DATOS DE LA TRANSACCIÓN", fmt_bold)

        columnas = list(tabla.columns.values)
        fmt_tabla_standard = workbook.add_format({
            "center_across": True, "text_wrap": True
        })

        data_rows = tabla.values.tolist()
        last_row_index = len(data_rows) + 25

        

        columns_config = [{"header": r, "header_format": fmt_merge_header ,"format": fmt_tabla_standard} for r in columnas]
        
        # Asignación de formatos a columnas específicas
        columns_config[0].update({"format": fmt_center})  # Nº Op
        columns_config[4].update({"format": fmt_money})   # Base Imp
        columns_config[5].update({"format": fmt_percent}) # Alícuota
        columns_config[7].update({"format": fmt_money})   # Imp. Muni
        columns_config[8].update({"format": fmt_money})   # Imp. Ret

        
            
        total_retained = sum(row[8] for row in data_rows)
        table_range = xlsxwriter.utility.xl_range(24, 0, last_row_index, len(columns_config) - 1)
        worksheet.add_table(table_range, {
            "data": data_rows, 
            "total_row": True, 
            "columns": columns_config, 
            "autofilter": False,
        })
        


        worksheet.write(last_row_index + 1, 7, "Total Retenido:", fmt_bold)
        worksheet.write(last_row_index + 1, 8, total_retained, fmt_money)

        # --- 7. FIRMAS ---
        row_signature = last_row_index + 12
        worksheet.write("B" + str(row_signature), "\t\tFirma del Agente de Retención", fmt_signature_line)
        worksheet.write("C" + str(row_signature), "", fmt_signature_line)
        worksheet.write("F" + str(row_signature), "Firma del Beneficiario", fmt_signature_line)

        # Firma configurada (Imagen)
        signature_rec = self.env["signature.config"].search([("active", "=", True)], limit=1, order="id asc")
        if signature_rec and signature_rec.signature:
            sig_img = tools.image_process(base64.b64decode(signature_rec.signature), (200, 200))
            worksheet.insert_image("B" + str(last_row_index + 7), 
                                   "signature.png", 
                                   {"image_data": BytesIO(sig_img),
                                    "x_offset": 60, "y_offset": 5,"x_scale": 1,"y_scale": 1})

        workbook.close()
        return data_io.getvalue()

    def get_xlsx_municipal_retention(self, retention_id):
        retention = self.env["account.retention"].browse(retention_id)
        lista = []
        
        base_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD", raise_if_not_found=False)

        for index, line in enumerate(retention.retention_line_ids):
            # Selección de montos
            if usd and base_currency == usd:
                invoice_amount = line.foreign_invoice_amount
                retention_amount = line.foreign_retention_amount
            else:
                invoice_amount = line.invoice_amount
                retention_amount = line.retention_amount

            # Crear el registro con nombres consistentes
            row = OrderedDict([
                ("Nº de la Op", index + 1),
                ("Fecha de Factura", line.move_id.invoice_date.strftime("%d-%m-%Y") if line.move_id.invoice_date else ""),
                ("Nº de Factura", line.move_id.name or ""),
                ("Nº de Control", line.move_id.correlative or ""),
                ("Base Imponible", invoice_amount or 0.0),
                ("Alícuota %", (line.aliquot / 100.0) if line.aliquot else 0.0), # NUMERO, NO F-STRING
                ("Actividad Económica", line.economic_activity_id.name or ""),
                ("Impuesto Municipal Retenido", retention_amount or 0.0),
                ("Impuesto Retenido", retention_amount or 0.0), # Consistencia de nombres
            ])
            lista.append(row)

        return pandas.DataFrame(lista).fillna(0)
    
    def _get_tax_authorities_record(self, company, retention_id):
        return company
