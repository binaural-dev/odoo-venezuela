from odoo import models, fields, _
from datetime import date
import xlsxwriter
from io import BytesIO
import pandas
from collections import OrderedDict
from dateutil.relativedelta import relativedelta


class MunicipalRetentionPatentReport(models.TransientModel):
    _name = "municipal.retention.patent.report"
    _description = "Municipal Retention Patent Report"

    date_start = fields.Date(required=True, default=date.today().replace(day=1))
    date_end = fields.Date(
        required=True,
        default=date.today().replace(day=1) + relativedelta(months=1, days=-1),
    )

    def print_xlsx(self):
        return {
            "type": "ir.actions.act_url",
            "url": "/web/get_xlsx_municipal_retention_report_patent?report_id=%s" % self.id,
            "target": "self",
        }

    def _xlsx_file(self, table, nombre):
        result = BytesIO()
        workbook = xlsxwriter.Workbook(result, {"in_memory": True})

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
        if len(table) == 0:
            return _("There is no data to show")
        worksheet2 = workbook.add_worksheet(nombre)
        worksheet2.set_column("A:Z", 20)
        worksheet2.set_row(0, 23, merge_format)
        worksheet2.set_row(0, 23, merge_format)
        columnas = list(table.columns.values)
        columns2 = [{"header": r} for r in columnas]
        currency_symbol = self.env.ref("base.VEF").symbol
        money_format = workbook.add_format({"num_format": '#,##0.00 "' + currency_symbol + '"'})
        columns2[3].update({"format": money_format})
        columns2[4].update({"format": money_format})
        columns2[5].update({"format": money_format})
        columns2[6].update({"format": money_format})
        columns2[7].update({"format": money_format})
        columns2[8].update({"format": money_format})
        columns2[9].update({"format": money_format})
        columns2[11].update({"format": money_format})
        columns2[13].update({"format": money_format})
        columns2[14].update({"format": money_format})
        columns2[15].update({"format": money_format})

        domain = self._get_xlsx_file_domain()

        invoice_lines = self.env["account.move.line"].search(domain)

        invoice_lines = invoice_lines.filtered(lambda l: l.price_unit > 0)
        usd_currency = self.env.ref("base.USD")
        company_currency = self.env.company.currency_id

        nc_financial = 0
        nd_financial = 0

        for line in invoice_lines:
            if line.move_id.move_type == "out_refund":
                if company_currency == usd_currency:
                    nc_financial += line.foreign_subtotal
                else:
                    nc_financial += line.price_subtotal
            if line.move_id.move_type == "out_invoice":
                if company_currency == usd_currency:
                    nd_financial += line.foreign_subtotal
                else:
                    nd_financial += line.price_subtotal

        data = table.values.tolist()
        col3 = len(columns2) - 1
        col2 = len(data) + 1
        cells = xlsxwriter.utility.xl_range(0, 0, col2, col3)

        worksheet2.hide_gridlines(2)
        worksheet2.add_table(
            cells, {"data": data, "total_row": True, "columns": columns2, "autofilter": False}
        )

        worksheet2.write("F" + str(col2 + 1), nc_financial, money_format)
        worksheet2.write("G" + str(col2 + 1), nd_financial, money_format)

        worksheet2.write_array_formula("D" + str(col2 + 1), f"=SUM(D2:D{col2})", money_format)
        worksheet2.write_array_formula("E" + str(col2 + 1), f"=SUM(E2:E{col2})", money_format)
        worksheet2.write_array_formula("H" + str(col2 + 1), f"=SUM(H2:H{col2})", money_format)
        worksheet2.write_array_formula("I" + str(col2 + 1), f"=SUM(I2:I{col2})", money_format)
        worksheet2.write_array_formula("J" + str(col2 + 1), f"=SUM(J2:J{col2})", money_format)
        worksheet2.write_array_formula("L" + str(col2 + 1), f"=SUM(L2:L{col2})", money_format)
        worksheet2.write_array_formula("N" + str(col2 + 1), f"=SUM(N2:N{col2})", money_format)
        worksheet2.write_array_formula("O" + str(col2 + 1), f"=SUM(O2:O{col2})", money_format)
        worksheet2.write_array_formula("P" + str(col2 + 1), f"=SUM(P2:P{col2})", money_format)

        for line in range(2, col2 + 1):
            worksheet2.write_array_formula(f"C{line}", f"=D{line}/D{str(col2+1)}", money_format)
            worksheet2.write_array_formula(f"F{line}", f"=C{line}*F{str(col2+1)}", money_format)
            worksheet2.write_array_formula(
                f"H{line}", f"=D{line}-E{line}-F{line}+G{line}", money_format
            )
            worksheet2.write_array_formula(f"G{line}", f"=G{str(col2+1)}*C{line}", money_format)
            worksheet2.write_array_formula(f"I{line}", f"=H{line}*0.9", money_format)
            worksheet2.write_array_formula(f"J{line}", f"=H{line}-I{line}", money_format)
            worksheet2.write_array_formula(f"L{line}", f"=I{line}*K{line}/100", money_format)
            worksheet2.write_array_formula(
                f"N{line}", f"=IF(L{line}>M{line},L{line},M{line})", money_format
            )
            worksheet2.write_array_formula(f"O{line}", f"=J{line}*K{line}/1000", money_format)
            worksheet2.write_formula(f"P{line}", f"=N{line}", money_format)

        workbook.close()
        return result.getvalue()

    def _get_xlsx_file_domain(self):
        return [
            ("move_id.invoice_date", ">=", self.date_start),
            ("move_id.invoice_date", "<=", self.date_end),
            ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
            ("move_id.financial_document", "=", True),
            ("move_id.state", "=", "posted"),
        ]

    def _get_xlsx_municipality_retention_report(self):
        domain = self._get_xlsx_municipality_retention_report_domain()
        invoice_lines = self.env["account.move.line"].search(domain)

        invoice_lines = invoice_lines.filtered(lambda l: any(l.ciu_id))

        groups = {}
        usd_currency = self.env.ref("base.USD")
        company_currency = self.env.company.currency_id

        for line in invoice_lines:
            price_subtotal = 0

            if company_currency == usd_currency:
                price_subtotal = line.foreign_subtotal
            else:
                price_subtotal = line.price_subtotal
            ciu = line.ciu_id
            if not ((ciu.name, line.product_id.categ_id.name) in groups.keys()):
                groups[ciu.name, line.product_id.categ_id.name] = {
                    "category_name": line.product_id.categ_id.name,
                    "CIU": ciu.name,
                    "sales_total": price_subtotal if line.move_id.move_type == "out_invoice" else 0,
                    "refund_total": price_subtotal if line.move_id.move_type == "out_refund" else 0,
                    "aliquot": ciu.aliquot,
                    "minimum_monthly": ciu.minimum_monthly,
                }
                continue

            groups[ciu.name, line.product_id.categ_id.name]["sales_total"] += (
                price_subtotal if line.move_id.move_type == "out_invoice" else 0
            )
            groups[ciu.name, line.product_id.categ_id.name]["refund_total"] += (
                price_subtotal if line.move_id.move_type == "out_refund" else 0
            )

        data = []
        cols = OrderedDict(
            [
                ("RUBROS", ""),
                ("CIU", ""),
                ("PRORRATA DEDUCCIONES", 0.0),
                ("VENTAS BRUTAS (Factura + ND)", 0.0),
                ("DEVOLUC. VENTAS (NC)", 0.0),
                ("DSTOS. VENTAS (NC Financiera)", 0.0),
                ("NOTAS DE DEBITO (ND financiera)", 0.0),
                ("INGRESOS 100%", 0.0),
                ("INGRESOS 90%", 0.0),
                ("INGRESOS 10%", 0.00),
                ("Alic %", ""),
                ("IMPUESTO", 0.00),
                ("MINIMO TRIBUTABLE", 0.00),
                ("ANTICIPO PERIODO", 0.00),
                ("IMPUESTO RESTANTE 10%", 0.00),
                ("ANTICIPO 90%", 0.00),
            ]
        )

        numero = 1
        for line in groups.keys():
            rows = OrderedDict()
            rows.update(cols)
            rows["RUBROS"] = groups[line]["category_name"]
            rows["CIU"] = groups[line]["CIU"]
            rows["VENTAS BRUTAS (Factura + ND)"] = groups[line]["sales_total"]
            rows["DEVOLUC. VENTAS (NC)"] = groups[line]["refund_total"]
            rows["Alic %"] = groups[line]["aliquot"]
            rows["MINIMO TRIBUTABLE"] = groups[line]["minimum_monthly"]

            data.append(rows)
            numero += 1
        table = pandas.DataFrame(data)
        return table.fillna(0)

    def _get_xlsx_municipality_retention_report_domain(self):
        return [
            ("move_id.invoice_date", ">=", self.date_start),
            ("move_id.invoice_date", "<=", self.date_end),
            ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
            ("move_id.financial_document", "=", False),
            ("move_id.state", "=", "posted"),
        ]
