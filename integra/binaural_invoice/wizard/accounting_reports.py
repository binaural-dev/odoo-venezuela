from dateutil.relativedelta import relativedelta
from datetime import datetime
from io import BytesIO
from odoo import models, fields
import xlsxwriter
from xlsxwriter import utility
import logging

_logger = logging.getLogger(__name__)
INIT_LINES = 8


class WizardAccountingReportsBinauralInvoice(models.TransientModel):
    _name = "wizard.accounting.reports"
    _description = "Wizard para generar reportes de libro de compra y ventas"
    _check_company_auto = True

    def _default_check_currency_system(self):
        is_system_currency_bs = self.env.company.currency_id.name == "VEF"
        return is_system_currency_bs

    def _default_date_from(self):
        current_day = fields.Date.today()
        return current_day

    def _default_date_to(self):
        current_day = self._default_date_from()
        final_day_month = relativedelta(months=1, days=-1)
        increment_date = current_day + final_day_month
        return increment_date

    def _default_company_id(self):
        company_id = self.env.company.id
        return company_id

    report = fields.Selection(
        [("purchase", "Book Purchase"), ("sale", "Sale Book")],
        string="Report",
        required=True,
    )

    date_from = fields.Date(string="Date Start", required=True, default=_default_date_from)

    date_to = fields.Date(
        string="Date End",
        required=True,
        default=_default_date_to,
    )

    company_id = fields.Many2one("res.company", default=_default_company_id)

    currency_system = fields.Boolean(string="Report in currency system", default=False)

    def _fields_sale_book_line(self, move, taxes):
        multiplier = -1 if move.move_type == "out_refund" else 1
        return {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date),
            "vat": move.vat,
            "partner_name": move.invoice_partner_display_name,
            "document_number": move.name,
            "move_type": self._determinate_type(move.move_type),
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": move.reversed_entry_id.name or "--",
            "correlative": move.correlative,
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "total_sales_iva": taxes.get("amount_taxed", 0) * multiplier,
            "total_sales_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
        }
    
    def _fields_purchase_book_line(self, move, taxes):
        multiplier = -1 if move.move_type == "in_refund" else 1
        return {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date),
            "vat": move.vat,
            "partner_name": move.invoice_partner_display_name,
            "document_number": move.name,
            "move_type": self._determinate_type(move.move_type),
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": move.reversed_entry_id.name or "--",
            "correlative": move.correlative,
            "reduced_aliquot": 0.08,
            "extend_aliquot": 0.31,
            "general_aliquot": 0.16,
            "total_purchases_iva": taxes.get("amount_taxed", 0),
            "total_purchases_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            "amount_extend_aliquot": taxes.get("amount_extend_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
            "tax_base_extend_aliquot": taxes.get("tax_base_extend_aliquot", 0) * multiplier,
        }

    def parse_sale_book_data(self):
        sale_book_lines = []
        moves = self.search_moves()

        for move in moves:
            taxes = self._determinate_amount_taxeds(move)
            sale_book_line = self._fields_sale_book_line(move, taxes)
            sale_book_lines.append(sale_book_line)
        return sale_book_lines

    def parse_purchase_book_data(self):
        purchase_book_lines = []
        moves = self.search_moves()

        for move in moves:
            taxes = self._determinate_amount_taxeds(move)
            purchase_book_line = self._fields_purchase_book_line(move, taxes)
            purchase_book_lines.append(purchase_book_line)

        return purchase_book_lines

    def _determinate_resume_books(self, moves, tax_type=None):
        resume_lines = []
        credit_notes = moves.filtered(lambda m: m.move_type in ["out_refund", "in_refund"])
        moves -= credit_notes

        if tax_type == "exempt_aliquot":
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["tax_base_exempt_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["amount_exempt_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["tax_base_exempt_aliquot"] * -1 for note in credit_notes]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["amount_exempt_aliquot"] * -1 for note in credit_notes]))

            return resume_lines
        if tax_type == "general_aliquot":
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["tax_base_general_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["amount_general_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["tax_base_general_aliquot"] * -1 for note in credit_notes]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["amount_general_aliquot"] * -1 for note in credit_notes]))

            return resume_lines
        if tax_type == "reduced_aliquot":
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["tax_base_reduced_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["amount_reduced_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["tax_base_reduced_aliquot"] * -1 for note in credit_notes]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["amount_reduced_aliquot"] * -1 for note in credit_notes]))

            return resume_lines
        if tax_type == "extend_aliquot":
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["tax_base_extend_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(move)["amount_extend_aliquot"] for move in moves]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["tax_base_extend_aliquot"] * -1 for note in credit_notes]))
            resume_lines.append(sum([self._determinate_amount_taxeds(note)["amount_extend_aliquot"] * -1 for note in credit_notes]))

            return resume_lines

        return [0.0, 0.0, 0.0, 0.0]

    def sale_book_fields(self):
        return [
            {
                "name": "N° operacion",
                "field": "index",
            },
            {
                "name": "Fecha del documento",
                "field": "document_date",
                "size": 15,
            },
            {
                "name": "Nombre/Razón Social",
                "field": "partner_name",
                "size": 25,
            },
            {
                "name": "Tipo",
                "field": "move_type",
                "size": 6,
            },
            {"name": "RIF", "field": "vat", "size": 15},
            {
                "name": "Nª de Control",
                "field": "correlative",
            },
            {
                "name": "N° de documento",
                "field": "document_number",
                "size": 20,
            },
            {
                "name": "N° Factura Afectada",
                "field": "number_invoice_affected",
                "size": 15,
            },
            {
                "name": "Total ventas con IVA",
                "field": "total_sales_iva",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Total ventas exentas",
                "field": "total_sales_not_iva",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Base imponible (16%)",
                "field": "tax_base_general_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Alicuota (16%)",
                "field": "general_aliquot",
                "format": "percent",
                "size": 15,
            },
            {
                "name": "IVA 16%",
                "field": "amount_general_aliquot",
                "format": "number",
            },
            {
                "name": "Base imponible (8%)",
                "field": "tax_base_reduced_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Alicuota (8%)",
                "field": "reduced_aliquot",
                "format": "percent",
                "size": 15,
            },
            {
                "name": "IVA 8%",
                "field": "amount_reduced_aliquot",
                "format": "number",
            },
        ]

    def purchase_book_fields(self):
        return [
            {
                "name": "N° operacion",
                "field": "index",
            },
            {
                "name": "Fecha del documento",
                "field": "document_date",
                "size": 15,
            },
            {
                "name": "Nombre/Razón Social",
                "field": "partner_name",
                "size": 25,
            },
            {
                "name": "Tipo",
                "field": "move_type",
                "size": 6,
            },
            {
                "name": "RIF", 
                "field": "vat", 
                "size": 15},
            {
                "name": "Nª de Control",
                "field": "correlative",
                "size": 15,
            },
            {
                "name": "N° de documento",
                "field": "document_number",
                "size": 20,
            },
            {
                "name": "N° Factura Afectada",
                "field": "number_invoice_affected",
                "size": 15,
            },
            {
                "name": "Total compras con IVA",
                "field": "total_purchases_iva",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Total compras exentas",
                "field": "total_purchases_not_iva",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Base imponible (16%)",
                "field": "tax_base_general_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Alicuota (16%)",
                "field": "general_aliquot",
                "format": "percent",
                "size": 15,
            },
            {
                "name": "IVA 16%",
                "field": "amount_general_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Base imponible (8%)",
                "field": "tax_base_reduced_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Alicuota (8%)",
                "field": "reduced_aliquot",
                "format": "percent",
                "size": 15,
            },
            {
                "name": "IVA 8%",
                "field": "amount_reduced_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Base imponible (31%)",
                "field": "tax_base_extend_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "Alicuota (31%)",
                "field": "extend_aliquot",
                "format": "percent",
                "size": 15,
            },
            {
                "name": "IVA 31%",
                "field": "amount_extend_aliquot",
                "format": "number",
                "size": 15,
            },
        ]

    def resume_book_headers(self):
        HEADERS = ("Base Imponible", "Débito Fiscal")

        return [
            {
                "name": "Resumen",
                "field": "resume",
                "headers": [
                    "",
                    "Débitos Fiscales",
                ],
            },
            {"name": "Facturas/Notas de Débito", "field": "inv_debit_notes", "headers": HEADERS},
            {
                "name": "Notas de Crédito",
                "field": "credit_notes",
                "headers": HEADERS,
            },
            {"name": "Total Neto", "field": "total", "headers": HEADERS},
        ]

    def _get_domain(self, current_company_id=False):
        search_domain = []
        is_purchase = self.report == "purchase"

        field_date = "date" if is_purchase else "invoice_date"

        if current_company_id:
            search_domain += [("company_id", "=", current_company_id)]

        move_type = (
            ["out_invoice", "out_refund"]
            if not is_purchase
            else ["in_invoice", "in_refund", "in_debit"]
        )

        search_domain += [(field_date, ">=", self.date_from)]
        search_domain += [(field_date, "<=", self.date_to)]
        search_domain += [
            ("state", "not in", ["draft"]),
            ("journal_id.fiscal", "=", True),
            ("move_type", "in", move_type),
        ]

        return search_domain

    def generate_report(self):
        is_sale = self.report == "sale"

        if is_sale:
            return self.download_sales_book()

        return self.download_purchases_book()

    def download_sales_book(self):
        self.ensure_one()
        url = "/web/download_sales_book"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def download_purchases_book(self):
        self.ensure_one()
        url = "/web/download_purchase_book"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _format_date(self, date):
        _fn = datetime.strptime(str(date), "%Y-%m-%d")
        return _fn.strftime("%d/%m/%Y")

    def _determinate_type(self, move_type):
        types = {
            "out_debit": "ND",
            "in_debit": "ND",
            "out_invoice": "FAC",
            "in_invoice": "FAC",
            "out_refund": "NC",
            "in_refund": "NC",
        }

        return types[move_type]

    def _determinate_transaction_type(self, move):
        if move.move_type in ["out_invoice", "in_invoice"] and move.state == "posted":
            return "01-REG"

        if move.move_type in ["out_debit", "in_debit"] and move.state == "posted":
            return "02-REG"

        if move.move_type in ["out_refund", "in_refund"] and move.state == "posted":
            return "03-REG"

        if move.move_type in [
            "out_refund",
            "out_debit",
            "out_invoice",
            "in_refund",
            "in_debit",
            "in_invoice",
        ] and move.state in ["cancel"]:
            return "03-ANU"
        

    def search_moves(self):
        env = self.env
        move_model = env["account.move"]
        domain = self._get_domain()
        moves = move_model.search(domain, order="invoice_date asc")
        return moves

    def _resume_sale_book_fields(self, moves):
        return [
            {
                "name": "Ventas Internas no Grabadas",
                "format": "number",
                "values": self._determinate_resume_books(moves, "exempt_aliquot"),
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General más Adicional",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
            {
                "name": "Ventas Internas Gravadas sólo por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves, "general_aliquot"),
            },
            {
                "name": "Ventas Internas Gravadas por Alícuota Reducida",
                "format": "number",
                "values": self._determinate_resume_books(moves, "reduced_aliquot"),
            },
            {
                "name": "Ajustes a los Débitos Fiscales de Periodos Anteriores",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
            {
                "name": "Total Ventas y Débitos Fiscales del Periodo",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
        ]

    def _resume_purchase_book_fields(self, moves):
        return [
            {
                "name": "Compras Internas no Grabadas",
                "format": "number",
                "values": self._determinate_resume_books(moves, "exempt_aliquot"),
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General más Adicional",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
            {
                "name": "Compras Internas Gravadas sólo por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves, "general_aliquot"),
            },
            {
                "name": "Compras Internas Gravadas por Alícuota General más Adicional",
                "format": "number",
                "values": self._determinate_resume_books(moves, "extend_aliquot"),
            },
            {
                "name": "Compras Internas Gravadas por Alícuota Reducida",
                "format": "number",
                "values": self._determinate_resume_books(moves, "reduced_aliquot"),
            },
            {
                "name": "Ajustes a los Créditos Fiscales de Periodos Anteriores",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
            {
                "name": "Total Compras y Créditos Fiscales del Periodo",
                "format": "number",
                "values": self._determinate_resume_books(moves)
            },
        ]

    def _determinate_amount_taxeds(self, move):
        is_posted = move.state == "posted"
        vef_base = self.company_id.currency_id.id == self.env.ref("base.VEF").id

        if not is_posted:
            return {
                "amount_untaxed": 0.0,
                "amount_taxed": 0.0,
                "tax_base_reduced_aliquot": 0.0,
                "tax_base_general_aliquot": 0.0,
                "tax_base_extend_aliquot": 0.0,
                "amount_reduced_aliquot": 0.0,
                "amount_general_aliquot": 0.0,
                "amount_extend_aliquot": 0.0,
            }

        is_credit_note = move.move_type in ["out_refund", "in_refund"]

        tax_totals = move.tax_totals

        tax_result = {}

        is_check_currency_system = self.currency_system

        if is_check_currency_system:
            fields_taxed = ("amount_untaxed", "amount_total", "groups_by_subtotal")
        else:
            fields_taxed = (
                "foreign_amount_untaxed",
                "foreign_amount_total",
                "groups_by_foreign_subtotal",
            )

        amount_untaxed = (
            tax_totals.get(fields_taxed[0]) * -1
            if is_credit_note and tax_totals.get(fields_taxed[0])
            else tax_totals.get(fields_taxed[0])
        )

        amount_taxed = (
            tax_totals.get(fields_taxed[1]) * -1
            if is_credit_note and tax_totals.get(fields_taxed[1])
            else tax_totals.get(fields_taxed[1])
        )

        tax_result.update(
            {
                "amount_untaxed": amount_untaxed,
                "amount_taxed": amount_taxed,
                "tax_base_reduced_aliquot": 0,
                "amount_reduced_aliquot": 0,
                "tax_base_general_aliquot": 0,
                "amount_general_aliquot": 0,
            }
        )

        is_currency_system = (
            "groups_by_subtotal"
            if vef_base or self.currency_system
            else "groups_by_foreign_subtotal"
        )
        tax_base = tax_totals.get(is_currency_system)

        for base in tax_base.items():
            taxes = base[1]

            for tax in taxes:
                tax_name = tax.get("tax_group_name")
                is_exempt = tax_name == "IVA 0%"
                if is_exempt:
                    tax_result.update(
                        {
                            "tax_base_exempt_aliquot": tax.get("tax_group_base_amount"),
                            "amount_exempt_aliquot": tax.get("tax_group_amount"),
                        }
                    )

                is_reduced_aliquot = tax_name == "IVA 8%"
                if is_reduced_aliquot:
                    tax_result.update(
                        {
                            "tax_base_reduced_aliquot": tax.get("tax_group_base_amount"),
                            "amount_reduced_aliquot": tax.get("tax_group_amount"),
                        }
                    )

                    continue

                is_general_aliquot = tax_name == "IVA 16%"
                if is_general_aliquot:
                    tax_result.update(
                        {
                            "tax_base_general_aliquot": tax.get("tax_group_base_amount"),
                            "amount_general_aliquot": tax.get("tax_group_amount"),
                        }
                    )

                    continue

                is_extend_aliquot = tax_name == "IVA 31%"
                if is_extend_aliquot:
                    tax_result.update(
                        {
                            "tax_base_extend_aliquot": tax.get("tax_group_base_amount"),
                            "amount_extend_aliquot": tax.get("tax_group_amount"),
                        }
                    )

        return tax_result

    def generate_sales_book(self):
        sale_book_lines = self.parse_sale_book_data()
        file = BytesIO()

        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
        worksheet = workbook.add_worksheet()

        # cell formats
        cell_bold = workbook.add_format(
            {"bold": True, "center_across": True, "text_wrap": True, "bottom": True}
        )
        merge_format = workbook.add_format(
            {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "gray"}
        )
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00"}),
            "percent": workbook.add_format({"num_format": "0.00%"}),
        }

        worksheet.merge_range(
            "D1:F1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({"bold": True, "center_across": True, "font_size": 18}),
        )
        worksheet.merge_range("D2:F2", "Libro de Ventas", cell_bold)
        worksheet.merge_range(
            "D3:F3",
            (
                f"Desde {self._format_date(self.date_from)}"
                f" Hasta {self._format_date(self.date_to)}"
            ),
            cell_bold,
        )

        name_columns = self.sale_book_fields()
        total_idx = 0

        for index, field in enumerate(name_columns):
            worksheet.set_column(index, index, len(field.get("name")) + 2)
            worksheet.merge_range(6, index, 7, index, field.get("name"), merge_format)

            for index_line, line in enumerate(sale_book_lines):
                total_idx = (8 + index_line) + 1

                if field["field"] == "index":
                    worksheet.write(INIT_LINES + index_line, index, index_line + 1)
                else:
                    cell_format = cell_formats.get(field.get("format"), workbook.add_format())
                    worksheet.write(INIT_LINES + index_line, index, line.get(field["field"]), cell_format)

            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}9:{col}{total_idx})", cell_formats.get("number")
                )

        self.generate_book_resume(worksheet, total_idx, merge_format, cell_formats)

        workbook.close()
        return file.getvalue()

    def generate_purchases_book(self):
        purchase_book_lines = self.parse_purchase_book_data()
        file = BytesIO()

        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
        worksheet = workbook.add_worksheet()

        # cell formats
        cell_bold = workbook.add_format(
            {"bold": True, "center_across": True, "text_wrap": True, "bottom": True}
        )
        merge_format = workbook.add_format(
            {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "gray"}
        )
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00"}),
            "percent": workbook.add_format({"num_format": "0.00%"}),
        }

        # header xml
        worksheet.merge_range(
            "D1:F1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({"bold": True, "center_across": True, "font_size": 18}),
        )
        worksheet.merge_range("D2:F2", "Libro de Compras", cell_bold)
        worksheet.merge_range(
            "D3:F3",
            (
                f"Desde {self._format_date(self.date_from)}"
                f" Hasta {self._format_date(self.date_to)}"
            ),
            cell_bold,
        )

        name_columns = self.purchase_book_fields()
        total_idx = 0

        for index, field in enumerate(name_columns):
            worksheet.set_column(index, index, len(field.get("name")) + 2)
            worksheet.merge_range(6, index, 7, index, field.get("name"), merge_format)

            for index_line, line in enumerate(purchase_book_lines):
                total_idx = (8 + index_line) + 1
                if field["field"] == "index":
                    worksheet.write(INIT_LINES + index_line, index, index_line + 1)
                else:
                    cell_format = cell_formats.get(field.get("format"), workbook.add_format())
                    worksheet.write(INIT_LINES + index_line, index, line.get(field["field"]), cell_format)

            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}9:{col}{total_idx})", cell_formats.get("number")
                )

        self.generate_book_resume(worksheet, total_idx, merge_format, cell_formats)

        workbook.close()
        return file.getvalue()

    def generate_book_resume(self, worksheet, index_to_start, merge_format, cell_formats):
        is_purchase = self.report == "purchase"
        header_idx = index_to_start + 2
        resume_headers = self.resume_book_headers()

        for idx, header in enumerate(resume_headers):
            nidx = idx * 2
            worksheet.merge_range(
                header_idx, nidx, header_idx, nidx + 1, header.get("name"), merge_format
            )
            worksheet.write(header_idx + 1, nidx, header.get("headers")[0])
            worksheet.write(header_idx + 1, nidx + 1, header.get("headers")[1])

        moves = self.search_moves()
        resume_columns = self._resume_purchase_book_fields(moves) if is_purchase else self._resume_sale_book_fields(moves)

        for idx, resume in enumerate(resume_columns):
            row_resume = (index_to_start + 4) +  idx

            worksheet.write(row_resume, 0, idx + 1)
            worksheet.write(row_resume, 1, resume.get("name"))

            total_line = 0
            for idx_line, line in enumerate(resume.get("values")):
                total_line = idx_line + 2
                worksheet.write(row_resume, idx_line + 2, line, cell_formats.get("number"))

            column_range = f"C{row_resume + 1}:{utility.xl_col_to_name(total_line)}{row_resume + 1}"
            imposed_formula = f"=SUMPRODUCT(--({column_range}), --(MOD(COLUMN({column_range}), 2)=1))"
            debit_formula = f"=SUMPRODUCT(--({column_range}), --(MOD(COLUMN({column_range}), 2)=0))"

            worksheet.write_formula(row_resume, total_line + 1, imposed_formula, cell_formats.get("number")) 
            worksheet.write_formula(row_resume, total_line + 2, debit_formula, cell_formats.get("number")) 