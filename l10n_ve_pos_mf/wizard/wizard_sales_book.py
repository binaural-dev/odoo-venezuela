from odoo import fields, models, _
from io import BytesIO
from datetime import datetime
from dateutil.relativedelta import relativedelta

import xlsxwriter


class SalesBookPOS(models.TransientModel):
    _name = "wizard.sales.book"
    _description = "Wizard to download xlsx of sakes Book POS"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", default=lambda self: self.env.user.company_id.id)
    date_from = fields.Date(required=True, default=datetime.today().replace(day=1))
    date_to = fields.Date(
        required=True, default=datetime.today().replace(day=1) + relativedelta(months=1, days=-1)
    )

    def _get_domain(self):
        search_domain = [
            "&",
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("state", "!=", "draft"),
            ("move_type", "in", ["out_invoice", "out_refund", "out_debit"]),
            "&",
            ("mf_serial", "!=", False),
            ("mf_reportz", "!=", False),
        ]
        return search_domain

    def get_lines_account_move(self):
        self.ensure_one()
        account_moves = self.env["account.move"].search(
            self._get_domain(), order="mf_invoice_number asc"
        )
        retention_invoices = self.env["account.retention"].search(
            [
                "&",
                ("date_accounting", "<=", self.date_to),
                ("date_accounting", ">=", self.date_from),
            ]
        )

        vef_base = self.company_id.currency_id.id == self.env.ref("base.VEF").id

        agrouped_by_report_z = {}

        for move in account_moves:
            if not agrouped_by_report_z.get(move.mf_reportz):
                agrouped_by_report_z[move.mf_reportz] = move
            else:
                agrouped_by_report_z[move.mf_reportz] |= move

        lines = []
        aliquot_16 = 16
        aliquot_8 = 8
        aliquot_31 = 31

        for report in agrouped_by_report_z.items():
            range_start = 0
            total_with_tax = 0
            total_exent = 0
            tax_base_16 = 0
            tax_amount_16 = 0
            tax_base_8 = 0
            tax_amount_8 = 0
            tax_base_31 = 0
            tax_amount_31 = 0
            iva_retention = 0

            for index, move in enumerate(report[1]):
                next_move = move
                is_last_move = False
                if (index + 1) < len(report[1]):
                    next_move = report[1][index + 1]
                else:
                    is_last_move = True

                if range_start == 0:
                    range_start = move.mf_invoice_number

                total_with_tax += move.amount_total if vef_base else move.foreign_amount_total

                amount_base = move.amount_by_group_base
                if not vef_base:
                    amount_base = move.foreign_amount_by_group_base

                for tax in amount_base:
                    if tax[0] == "Total G 16%":
                        tax_base_16 += tax[1]
                        tax_amount_16 += tax[2]
                    if tax[0] == "Total G 8%":
                        tax_base_8 += tax[1]
                        tax_amount_8 += tax[2]
                    if tax[0] == "Total G 31%":
                        tax_base_31 += tax[1]
                        tax_amount_31 += tax[2]
                    if tax[0] == "Total G 0%":
                        total_exent += tax[1]

                if move.move_type == "out_invoice":
                    if (
                        (
                            (
                                self._format_date(move.invoice_date)
                                != self._format_date(next_move.invoice_date)
                            )
                            or next_move.partner_id.prefix_vat == "J"
                            or next_move.partner_id.taxpayer == "special"
                            or next_move.move_type != "out_invoice"
                        )
                        or is_last_move
                    ) and move.partner_id.taxpayer == "ordinary":
                        lines_to_sales_book = {
                            "date": self._format_date(move.invoice_date),
                            "vat": "RESUMEN",
                            "partner_name": "Resumen Diario de Ventas",
                            "invoices": f"Desde {range_start} Hasta {move.mf_invoice_number}",
                            "mf_serial": move.mf_serial,
                            "reportz": move.mf_reportz,
                            "type": move.sales_book_type,
                            "invoice_affected": "",
                            "date_retention_receipt": "",
                            "retention_receipt": "",
                            "total_with_tax": total_with_tax,
                            "total_without_tax": total_exent,
                            "tax_base_16": tax_base_16,
                            "tax_amount_16": tax_amount_16,
                            "aliquot_16": aliquot_16,
                            "tax_base_8": tax_base_8,
                            "tax_amount_8": tax_amount_8,
                            "aliquot_8": aliquot_8,
                            "tax_base_31": tax_base_31,
                            "tax_amount_31": tax_amount_31,
                            "aliquot_31": aliquot_31,
                            "iva_retention": iva_retention,
                        }

                        lines.append(lines_to_sales_book)
                        range_start = 0
                        total_with_tax = 0
                        total_exent = 0
                        tax_base_16 = 0
                        tax_amount_16 = 0
                        tax_base_8 = 0
                        tax_amount_8 = 0
                        tax_base_31 = 0
                        tax_amount_31 = 0
                        iva_retention = 0
                        continue
                    if not is_last_move and move.partner_id.taxpayer == "ordinary":
                        continue

                total_current = move.amount_total
                if vef_base:
                    total_current = move.foreign_amount_total

                date_retention = False
                retention_receipt = False

                if (
                    move.retention_iva_line_ids
                    and move.iva_voucher_number in retention_invoices.mapped("number")
                ):
                    date_retention = move.retention_iva_line_ids[0].retention_id.date_accounting
                    retention_receipt = move.retention_iva_line_ids[0].retention_id.number
                    iva_retention = sum(move.retention_iva_line_ids.mapped("retention_amount"))
                    if not vef_base:
                        iva_retention = sum(
                            move.retention_iva_line_ids.mapped("foreign_retention_amount")
                        )

                if move.move_type == "out_refund":
                    total_current = total_current * -1
                    total_with_tax = total_with_tax * -1
                    total_exent = total_exent * -1
                    tax_base_16 = tax_base_16 * -1
                    tax_amount_16 = tax_amount_16 * -1
                    tax_base_8 = tax_base_8 * -1
                    tax_amount_8 = tax_amount_8 * -1
                    tax_base_31 = tax_base_31 * -1
                    tax_amount_31 = tax_amount_31 * -1
                    iva_retention = iva_retention * -1

                lines_to_sales_book = {
                    "date": self._format_date(move.invoice_date),
                    "vat": move.vat,
                    "partner_name": move.partner_id.name,
                    "invoices": move.mf_invoice_number,
                    "mf_serial": move.mf_serial,
                    "reportz": move.mf_reportz,
                    "type": move.sales_book_type,
                    "invoice_affected": move.reversed_entry_id.mf_invoice_number
                    if move.reversed_entry_id
                    else "",
                    "date_retention_receipt": self._format_date(date_retention)
                    if date_retention
                    else "",
                    "retention_receipt": retention_receipt or "",
                    "total_with_tax": total_current,
                    "total_without_tax": total_exent,
                    "tax_base_16": tax_base_16,
                    "aliquot_16": aliquot_16,
                    "tax_amount_16": tax_amount_16,
                    "tax_base_8": tax_base_8,
                    "aliquot_8": aliquot_8,
                    "tax_amount_8": tax_amount_8,
                    "tax_base_31": tax_base_31,
                    "tax_amount_31": tax_amount_31,
                    "aliquot_31": aliquot_31,
                    "iva_retention": iva_retention,
                }
                range_start = 0
                total_with_tax = 0
                total_exent = 0
                tax_base_16 = 0
                tax_amount_16 = 0
                tax_base_8 = 0
                tax_amount_8 = 0
                tax_base_31 = 0
                tax_amount_31 = 0
                iva_retention = 0

                lines.append(lines_to_sales_book)

        not_moves = None

        for retention in retention_invoices:
            for line in retention.retention_line:
                if line.invoice_id in account_moves:
                    continue
                if not not_moves or len(not_moves) == 0:
                    not_moves = line.invoice_id
                else:
                    not_moves |= line.invoice_id

        lines.sort(key=lambda x: x["reportz"])

        if not not_moves or len(not_moves) == 0:
            return lines

        for move in not_moves:

            date_retention = move.retention_iva_line_ids[0].retention_id.date_accounting
            retention_receipt = move.retention_iva_line_ids[0].retention_id.number
            iva_retention = sum(move.retention_iva_line_ids.mapped("retention_amount"))
            if not vef_base:
                iva_retention = sum(move.retention_iva_line_ids.mapped("foreign_retention_amount"))

            lines_to_sales_book = {
                "date": self._format_date(move.invoice_date),
                "vat": move.vat,
                "partner_name": move.partner_id.name,
                "invoices": move.mf_invoice_number,
                "mf_serial": move.mf_serial,
                "reportz": move.mf_reportz,
                "type": move.sales_book_type,
                "invoice_affected": move.reversed_entry_id.mf_invoice_number
                if move.reversed_entry_id
                else "",
                "date_retention_receipt": self._format_date(date_retention)
                if date_retention
                else "",
                "retention_receipt": retention_receipt or "",
                "total_with_tax": 0,
                "total_without_tax": 0,
                "tax_base_16": 0,
                "aliquot_16": aliquot_16,
                "tax_amount_16": 0,
                "tax_base_8": 0,
                "aliquot_8": aliquot_8,
                "tax_amount_8": 0,
                "tax_base_31": 0,
                "tax_amount_31": 0,
                "aliquot_31": aliquot_31,
                "iva_retention": iva_retention,
            }

            lines.append(lines_to_sales_book)

        lines.sort(key=lambda x: x["reportz"])
        return lines

    def sales_book_fields(self):
        return [
            {"name": "N° operacion", "field": "index"},
            {"name": "Fecha documento", "field": "date"},
            {"name": "RIF", "field": "vat", "size": 15},
            {"name": "Nombre o Razón Social", "field": "partner_name", "size": 25},
            {"name": "N° de documento", "field": "invoices", "size": 30},
            {"name": "Registro de maquina fiscal", "field": "mf_serial"},
            {"name": "N° Reporte Z", "field": "reportz"},
            {"name": "Tipo", "field": "type"},
            {"name": "N° Factura Afectada", "field": "invoice_affected", "size": 15},
            {"name": "Total ventas con IVA", "field": "total_with_tax", "size": 25, "number": True},
            {
                "name": "Total ventas exentas",
                "field": "total_without_tax",
                "size": 20,
                "number": True,
            },
            {"name": "Base imponible", "field": "tax_base_16", "size": 20, "number": True},
            {"name": "Alícuota", "field": "aliquot_16", "size": 7},
            {"name": "IVA 16%", "field": "tax_amount_16", "size": 20, "number": True},
            {"name": "Base imponible", "field": "tax_base_8", "size": 20, "number": True},
            {"name": "Alícuota", "field": "aliquot_8", "size": 7},
            {"name": "IVA 8%", "field": "tax_amount_8", "size": 20, "number": True},
            {"name": "Base imponible", "field": "tax_base_31", "size": 20, "number": True},
            {"name": "Alícuota", "field": "aliquot_31", "size": 7},
            {"name": "IVA 31%", "field": "tax_amount_31", "size": 20, "number": True},
            {"name": "Fecha Retencion", "field": "date_retention_receipt"},
            {"name": "N° Retencion", "field": "retention_receipt", "size": 15},
            {
                "name": "IVA retenido",
                "field": "iva_retention",
                "size": 15,
                "number": True,
            },
        ]

    def sales_book_abstract(self):
        return [
            {"name": "Resumen del diario", "field": "total"},
            {"name": "Total ventas internas No Gravadas", "field": ""},
            {"name": "Total ventas exportacion", "field": ""},
            {"name": "Total de las Ventas afectadas  en alícuota General", "field": ""},
            {"name": "Total de las Ventas Internas Afectadas en alícuota Reducida", "field": ""},
            {"name": "Total Ventas afectadas  en alícuota General + Adicional", "field": ""},
            {"name": "IVA Retenido", "field": ""},
            {"name": "Ajuste a los Debito fiscales de períodos anteriores", "field": ""},
        ]

    def generate_sales_book(self, date_from, date_to):
        file = BytesIO()
        for record in self:
            record.date_from = date_from
            record.date_to = date_to

            lines = record.get_lines_account_move()

            workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
            worksheet = workbook.add_worksheet()

            # cell formats
            cell_bold = workbook.add_format(
                {"bold": True, "center_across": True, "text_wrap": True, "bottom": True}
            )
            cell_number = workbook.add_format({"num_format": "#,##0.00"})
            cell_bold_abstract = workbook.add_format({"bold": True})

            worksheet.set_column(1, 29, 10)
            worksheet.set_column(5, 5, 15)

            # header xml
            worksheet.merge_range(
                "D1:F1",
                f"{record.company_id.name} - {record.company_id.vat}",
                workbook.add_format({"bold": True, "center_across": True, "font_size": 18}),
            )
            worksheet.merge_range("D2:F2", "Libro de Ventas", cell_bold)
            worksheet.merge_range(
                "D3:F3",
                (
                    f"Desde {record._format_date(record.date_from)}"
                    f" Hasta {record._format_date(record.date_to)}"
                ),
                cell_bold,
            )

            # fields

            for index, field in enumerate(record.sales_book_fields()):
                if field.get("size"):
                    worksheet.set_column(index, index, field.get("size"))
                worksheet.merge_range(6, index, 7, index, field["name"], cell_bold)
                for index_line, line in enumerate(lines):
                    if field["field"] == "index":
                        worksheet.write(8 + index_line, index, index_line + 1)
                    else:
                        if field.get("number"):
                            worksheet.write(
                                8 + index_line, index, line[field["field"]], cell_number
                            )
                        else:
                            worksheet.write(8 + index_line, index, line[field["field"]])
                if field.get("number"):
                    row_start = xlsxwriter.utility.xl_rowcol_to_cell(8, index)
                    row_end = xlsxwriter.utility.xl_rowcol_to_cell(7 + len(lines), index)
                    result_total = f"=SUM({row_start}:{row_end})"

                    if field["field"] == "total_without_tax":
                        worksheet.write_formula(13 + len(lines), 4, result_total, cell_number)

                    if field["field"] == "tax_base_16":
                        worksheet.write_formula(15 + len(lines), 4, result_total, cell_number)

                    if field["field"] == "tax_amount_16":
                        worksheet.write_formula(15 + len(lines), 5, result_total, cell_number)

                    if field["field"] == "tax_base_8":
                        worksheet.write_formula(16 + len(lines), 4, result_total, cell_number)

                    if field["field"] == "tax_amount_8":
                        worksheet.write_formula(
                            16 + len(lines),
                            5,
                            result_total,
                            cell_number,
                        )

                    if field["field"] == "tax_base_31":
                        worksheet.write_formula(17 + len(lines), 4, result_total, cell_number)

                    if field["field"] == "tax_amount_31":
                        worksheet.write_formula(17 + len(lines), 5, result_total, cell_number)

                    if field["field"] == "iva_retention":
                        worksheet.write_formula(
                            18 + len(lines),
                            5,
                            result_total,
                            workbook.add_format({"num_format": "#,##0.00"}),
                        )

                    worksheet.write_formula(
                        8 + len(lines),
                        index,
                        result_total,
                        workbook.add_format({"num_format": "#,##0.00", "top": True, "bold": True}),
                    )

            for index, field in enumerate(record.sales_book_abstract()):
                worksheet.merge_range(
                    12 + len(lines) + index,
                    0,
                    12 + len(lines) + index,
                    3,
                    field["name"],
                    cell_bold_abstract,
                )
            worksheet.write(12 + len(lines), 4, "Base Imponibles", cell_bold)
            worksheet.write(12 + len(lines), 5, "Débito Fiscal", cell_bold)

            worksheet.write_number(
                19 + len(lines), 5, 0.00, workbook.add_format({"num_format": "#,##0.00"})
            )

            workbook.close()
            return file.getvalue()

    def download_sales_book(self):
        self.ensure_one()
        url = f"/web/binary/download_sales_book?&date_from={self.date_from}&date_to={self.date_to}"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _format_date(self, date):
        _fn = datetime.strptime(str(date), "%Y-%m-%d")
        return _fn.strftime("%d/%m/%Y")
