from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError
import xlsxwriter
from datetime import datetime, date
from io import BytesIO
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
import pandas as pd
from odoo.http import request
import os

import logging
_logger = logging.getLogger(__name__)


class RetentionIslrReport(models.TransientModel):
    _name = "wizard.retention.islr"
    _description = "Wizard Retention ISLR Report"

    check_company = True

    report = fields.Selection(
        [
            ("islr", "Islr Retention"),
        ],
        "Report type",
        required=True,
    )
    date_start = fields.Date("Date start", default=date.today().replace(day=1))
    date_end = fields.Date(
        "Date end", default=date.today().replace(day=1) + relativedelta(months=1, days=-1)
    )
    file = fields.Binary(readonly=True)
    filename = fields.Char()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.user.company_id.id)

    def download_format(self):
        ext = ""
        if self.report == "islr":
            # ext = '.xlsx'
            # macro
            ext = ".xlsm"
        else:
            ext = ".xlsx"
        return ext

    def _get_domain(self, current_company_id=False):
        search_domain = []
        search_domain += [("date_accounting", ">=", self.date_start)]
        search_domain += [("date_accounting", "<=", self.date_end)]

        if current_company_id:
            search_domain += [("company_id", "=", current_company_id.id)]

        return search_domain

    def print_report(self):
        current_company = self.env.company
        report = self.report
        filecontent = "5"

        report_obj = request.env["wizard.retention.islr"]

        table = report_obj._table_retention_islr(int(self.id))
        name = "XML Retencion de ISLR"
        start = str(self.date_start)
        end = str(self.date_end)
        if not table.empty and name:
            if report == "islr":
                filecontent = report_obj._excel_file_retention_islr(
                    table, name, start, end, current_company
                )
        if not filecontent:
            raise UserError(_("No data to export"))
        return {
            "type": "ir.actions.act_url",
            "url": "/web/download_islr_report?report=%s&wizard=%s&start=%s&end=%s&current_company_id=%s"
            % (
                self.report,
                self.id,
                str(self.date_start),
                str(self.date_end),
                str(current_company.id),
            ),
            "target": "self",
        }

    def _excel_file_retention_islr(self, table, name, start, end, current_company):
        company = current_company
        data2 = BytesIO()
        workbook = xlsxwriter.Workbook(data2, {"in_memory": True})
        merge_format = workbook.add_format(
            {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "gray"}
        )
        datos = table
        company_vat = company.vat if company.vat else ""
        range_month = datetime.strptime(start, "%Y-%m-%d").strftime("%Y%m")

        worksheet2 = workbook.add_worksheet(name)
        worksheet2.set_column("A:Z", 20)
        worksheet2.merge_range("A1:F1", name, merge_format)
        worksheet2.write("G1", "Rif Agente:")
        worksheet2.write("H1", company_vat)
        worksheet2.write("G2", "Periodo")
        worksheet2.write("H2", range_month)
        worksheet2.merge_range("A2:B2", "Ruta de descarga:", merge_format)
        worksheet2.write("C2", "C:/Users/Public/")
        columnas = list(datos.columns.values)
        columns2 = [{"header": r} for r in columnas]
        data = datos.values.tolist()
        # para macro, cantidad de lineas
        worksheet2.write("I1", len(data))
        currency_format = workbook.add_format({"num_format": "#,###0.00"})
        date_format = workbook.add_format()
        date_format.set_num_format("d-mmm-yy")  # Format string.
        col3 = len(columns2) - 1
        col2 = len(data) + 4
        for record in columns2[6:8]:
            record.update({"format": currency_format})
        cells = xlsxwriter.utility.xl_range(3, 0, col2, col3)
        worksheet2.add_table(cells, {"data": data, "total_row": False, "columns": columns2})
        # macro
        url = os.path.dirname(os.path.abspath(__file__))

        workbook.add_vba_project(url + "/vbaProject.bin")
        worksheet2.insert_button(
            "I2", {"macro": "MakeXML", "caption": "Generar XML", "width": 120, "height": 30}
        )

        workbook.close()
        data2 = data2.getvalue()
        return data2

    @api.model
    def _get_retention_islr_excel_model_row(self):
        
        new_model_row = OrderedDict(
            [
                ("ID Sec", 0),
                ("RIF Retenido", ""),
                ("Número factura", ""),
                ("Control Número", ""),
                ("Fecha Operación", ""),
                ("Código Concepto", ""),
                ("Monto Operación", 0.00),
                ("Porcentaje de retención", 0.00),
            ]
        )
        
        return new_model_row

    @api.model    
    def _get_retention_islr_excel_row(self, row_idx, ret_line_id, is_vef_currency):

        new_row = self._get_retention_islr_excel_model_row()

        ret_id = ret_line_id.retention_id

        new_row["ID Sec"] = row_idx

        new_row["RIF Retenido"] = ret_id.partner_id.prefix_vat + ret_id.partner_id.vat

        pi = str(ret_id.date_accounting)

        fpi = datetime.strptime(pi, "%Y-%m-%d")

        new_row["Número factura"] = ret_line_id.move_id.name[-10:] if len(ret_line_id.move_id.name) > 10 else ret_line_id.move_id.name

        new_row["Control Número"] = ret_line_id.move_id.correlative

        new_row["Fecha Operación"] = fpi.strftime("%d/%m/%Y")

        concept = ""
        alicuota = ""

        for l_pay_concept_id in ret_line_id.payment_concept_id.line_payment_concept_ids:
            if l_pay_concept_id.type_person_id.name == ret_id.partner_id.type_person_id.name:
                concept = l_pay_concept_id.code
                alicuota = l_pay_concept_id.tariff_id.percentage if l_pay_concept_id.tariff_id else ""
                break

        new_row["Código Concepto"] = concept

        new_row["Monto Operación"] = (
            round(ret_line_id.foreign_invoice_amount, 2) if is_vef_currency else ret_line_id.invoice_amount
        )

        new_row["Porcentaje de retención"] = alicuota

        return new_row

    def _get_retention_ids(self, current_company=False):
        search_domain = self._get_domain(current_company)

        search_domain += [
            ("type", "in", ["in_invoice"]),
            ("type_retention", "in", ["islr"]),
            ("state", "in", ["emitted"]),
        ]

        retention_ids = self.env["account.retention"].search(search_domain, order="id asc")

        return retention_ids

    def _get_retention_islr_excel_rows(self, table_rows, row_idx, current_company=False):
        is_vef_currency = self.env.ref("base.VEF").id == self.env.company.currency_foreign_id.id

        retention_ids = self._get_retention_ids(current_company)
        
        if not retention_ids:
            raise ValidationError(_("No withholdings have been found in the selected period"))

        retention_line_ids = retention_ids.mapped("retention_line_ids")

        for retention_line_id in retention_line_ids:
            row_idx += 1

            new_row = self._get_retention_islr_excel_row(row_idx, retention_line_id, is_vef_currency)

            table_rows.append(new_row)


        return table_rows, row_idx

    def _get_table_rows_sorted(self, table_rows):
        table_rows = sorted(table_rows, key=lambda row: datetime.strptime(row['Fecha Operación'], "%d/%m/%Y"))

        return table_rows

    def _retention_islr_excel(self, current_company=False):
        table_rows, table_rows_count = self._get_retention_islr_excel_rows([], 0, current_company)

        table_rows = self._get_table_rows_sorted(table_rows)

        table = pd.DataFrame(table_rows)

        return table

    def _table_retention_islr(self, wizard=False, current_company=False):
        if wizard:
            wiz = self.search([("id", "=", wizard)])
        else:
            wiz = self
        tabla1 = wiz._retention_islr_excel(current_company)
        union = pd.concat([tabla1])
        return union
