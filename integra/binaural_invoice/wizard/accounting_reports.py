from dateutil.relativedelta import relativedelta
from datetime import datetime
from io import BytesIO
from odoo import models, fields
import xlsxwriter
import logging

_logger = logging.getLogger(__name__)


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

    date_from = fields.Date(
        string="Date Start",
        required=True,
        default=_default_date_from
    )

    date_to = fields.Date(
        string="Date End",
        required=True,
        default=_default_date_to,
    )

    company_id = fields.Many2one("res.company", default=_default_company_id)

    currency_system = fields.Boolean(
        string="Report in currency system",
        default=_default_check_currency_system
    )

    def parse_sale_book_data(self):
        sale_book_lines = []
        moves = self.search_moves()

        for count, move in enumerate(moves):
            taxes = self._determinate_amount_taxeds(move)

            sale_book_line = {
                "operation_number": count + 1,
                "document_date": self._format_date(move.date),
                "vat": move.vat,
                "partner_name": move.invoice_partner_display_name,
                "document_number": move.name,
                "move_type": self._determinate_type(move.move_type),
                "transaction_type": self._determinate_transaction_type(move),
                "number_invoice_affected": move.reversed_entry_id.name or "",
                "correlative": move.correlative or "",
                "IVA8%": "8",
                "IVA16%": "16",
                "total_sales_iva": taxes.get("amount_taxed") or 0,
                "total_sales_not_iva": taxes.get("amount_untaxed") or 0,
                "aliquot_8": taxes.get("aliquot_8") or 0,
                "aliquot_16": taxes.get("aliquot_16") or 0,
                "tax_base_8": taxes.get("tax_base_8") or 0,
                "tax_base_16": taxes.get("tax_base_16") or 0,
            }

            sale_book_lines.append(sale_book_line)

        return sale_book_lines

    def sale_book_fields(self):
        return [
            "N° operación",
            "Fecha del documentó",
            "RIF",
            "Nombre/Razón Social",
            "Tipo",
            "N° de Documento",
            "Nª de Control",
            "Tipo de Transacción",
            "N° Factura Afectada",
            "Total ventas con IVA",
            "Total ventas exentas",
            "Base imponible (16%)",
            "IVA 16%",
            "Alicuota (16%)",
            "Base imponible (8%)",
            "IVA 8%",
            "Alicuota (8%)",
            "Fecha Retención",
            "N° Retención",
            "IVA retenido"
        ]

    def purchase_book_fields(self):
        return [
            "N° operación",
            "Fecha del documentó",
            "RIF",
            "Nombre/Razón Social",
            "Tipo",
            "N° de Documento",
            "Nª de Control",
            "Tipo de Transacción",
            "N° Factura Afectada",
            "Total ventas con IVA",
            "Total ventas exentas",
            "Base imponible (16%)",
            "IVA 16%",
            "Alicuota (16%)",
            "Base imponible (8%)",
            "IVA 8%",
            "Alicuota (8%)",
            "Base imponible (31%)",
            "IVA 31%",
            "Alicuota (31%)",
            "Fecha Retención",
            "N° Retención",
            "IVA retenido"
        ]

    def _get_domain(self, current_company_id=False):
        search_domain = []
        is_purchase = self.report == "purchase"

        field_date = "invoice_date" if is_purchase else "date"

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
        is_sale = self.report == 'sale'

        if is_sale:
            return self.download_sales_book()

        return self.download_purchases_book()

    def download_sales_book(self):
        self.ensure_one()
        url = "/web/download_sales_book"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def download_purchases_book(self):
        self.ensure_one()
        url = "/web/download_purchases_book"
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
            "in_refund": "NC"
        }

        return types[move_type]

    def _determinate_transaction_type(self, move):
        if move.move_type in ["out_invoice", "in_invoice"] and move.state == "posted":
            return "01-REG"

        if move.move_type in ["out_debit", "in_debit"] and move.state == "posted":
            return "02-REG"

        if move.move_type in ["out_refund", "in_refund"] and move.state == "posted":
            return "03-REG"

        if move.move_type in ["out_refund", "out_debit", "out_invoice", "in_refund", "in_debit", "in_invoice"] and move.state in ["cancel"]:
            return "03-ANU"

    def search_moves(self):
        env = self.env
        move_model = env['account.move']
        domain = self._get_domain()
        moves = move_model.search(domain)
        return moves

    def _resume_book_fields(self, row_total):
        return [
            {
                "name": "Ventas Internas no Grabadas",
                "fac_calc": f"=K{row_total + 1}",
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General",
                "fac_calc": 0.0,
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General más Adicional",
                "fac_calc": 0.0,
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Ventas Internas Gravadas sólo por Alícuota General",
                "fac_calc": f"=L{row_total + 1}",
                "fac_debit_fiscal": f"=N{row_total + 1}",
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Ventas Internas Gravadas por Alícuota General más Adicional",
                "fac_calc": 0.0,
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Ventas Internas Gravadas por Alícuota Reducida",
                "fac_calc": f"=K{row_total + 1}",
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Ajustes a los Débitos Fiscales de Periodos Anteriores",
                "fac_calc": 0.0,
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {

                "name": "Total Ventas y Débitos Fiscales del Periodo",
                "fac_calc": f"=K{row_total + 1}",
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            },
            {
                "name": "Total Retenciones",
                "fac_calc": 0.0,
                "fac_debit_fiscal": 0.0,
                "nc_calc": 0.0,
                "nc_debit_fiscal": 0.0,
                "tn_calc": 0.0,
                "tn_debit_fiscal": 0.0
            }
        ]


    def generate_sales_book(self):
        sale_book_lines = self.parse_sale_book_data()
        file = BytesIO()

        workbook = xlsxwriter.Workbook(file, {
            "in_memory": True, "nan_inf_to_errors": True
        })

        worksheet = workbook.add_worksheet()

        cell_bold = workbook.add_format({
            "bold": True,
            "center_across": True,
            "text_wrap": True,
            "bottom": True
        })

        merge_format = workbook.add_format({
            'bold': 1,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': 'gray'
        })

        worksheet.set_column(0, 29, 20)
        worksheet.set_column(5, 5, 40)

        worksheet.merge_range(
            "D1:F1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({
                "bold": True,
                "center_across": True,
                "font_size": 18
            }),
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
        init_col = 0
        init_row = 4
        history_row = init_row

        for count, name in enumerate(name_columns):
            col = init_col + count
            worksheet.write(init_row, col, name, merge_format)

            is_sale_general = name == "Base imponible (16%)"
            if is_sale_general:
                worksheet.merge_range(
                    'L4:N4',
                    'Ventas Internas Alicuota General',
                    merge_format
                )

            is_sale_reduce = name == "Base imponible (8%)"
            if is_sale_reduce:
                worksheet.merge_range(
                    'O4:Q4',
                    'Ventas Internas Alicuota Reducida',
                    merge_format
                )

        for count, line in enumerate(sale_book_lines):
            row = init_row + count + 1
            col = init_col

            if row % 2 == 0:
                color = "b8cce4"
            else:
                color = "dbe5f1"

            dic_format_base = {
                "fg_color": color,
                "border": 1
            }

            dic_format_extend = {
                "fg_color": color,
                "border": 1,
                "num_format": "#,##0.00"
            }

            format_1 = workbook.add_format(dic_format_base)
            format_2 = workbook.add_format(dic_format_extend)

            worksheet.write(row, col, line["operation_number"], format_1)
            worksheet.write(row, col + 1, line["document_date"], format_1)
            worksheet.write(row, col + 2, line["vat"], format_1)
            worksheet.write(row, col + 3, line["partner_name"], format_1)
            worksheet.write(row, col + 4, line["move_type"], format_1)
            worksheet.write(row, col + 5, line["document_number"], format_1)
            worksheet.write(row, col + 6, line["correlative"], format_1)
            worksheet.write(row, col + 7, line["transaction_type"], format_1)
            worksheet.write(
                row,
                col + 8,
                line["number_invoice_affected"],
                format_1
            )
            worksheet.write(row, col + 9, line["total_sales_iva"], format_2)
            worksheet.write(
                row,
                col + 10,
                line["total_sales_not_iva"],
                format_2
            )
            worksheet.write(row, col + 11, line.get("tax_base_16"), format_2)
            worksheet.write(row, col + 12, line.get("IVA16%"), format_1)
            worksheet.write(row, col + 13, line.get("aliquot_16"), format_2)
            worksheet.write(row, col + 14, line.get("tax_base_8"), format_2)
            worksheet.write(row, col + 15, line.get("IVA8%"), format_1)
            worksheet.write(row, col + 16, line.get("aliquot_8"), format_2)
            worksheet.write(row, col + 17, "", format_1)
            worksheet.write(row, col + 18, "", format_1)
            worksheet.write(row, col + 19, "", format_1)

            history_row = row

        row_total = history_row + 1

        format_col_total = workbook.add_format({
            "num_format": "#,##0.00",
            "fg_color": "4f81bd",
        })

        only_color_format = workbook.add_format({"fg_color": "4f81bd"})

        is_totals_cols = ["J", "K", "L", "N", "O", "Q"]
        is_full_cols_total = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "S",
            "T"
        ]

        for index, column in enumerate(is_full_cols_total):
            is_first_col = index == 0
            if is_first_col:
                worksheet.write(row_total, index, "Total", only_color_format)
                continue

            is_column_total = column in is_totals_cols
            if is_column_total:
                worksheet.write_formula(
                    f"{column}{row_total + 1}",
                    f"=SUM({column}{init_row + 2}:{column}{history_row + 1})",
                    format_col_total
                )
                continue

            worksheet.write(row_total, index, "", only_color_format)

        resume_row_init = history_row + 4

        worksheet.merge_range(
            f"A{resume_row_init}:B{resume_row_init}",
            "Resumen",
            merge_format
        )

        worksheet.merge_range(
            f"C{resume_row_init}:D{resume_row_init}",
            "Facturas/Notas de Débito",
            merge_format
        )

        worksheet.merge_range(
            f"E{resume_row_init}:F{resume_row_init}",
            "Notas de Crédito",
            merge_format
        )

        worksheet.merge_range(
            f"G{resume_row_init}:H{resume_row_init}",
            "Total Neto",
            merge_format
        )

        worksheet.write(
            resume_row_init,
            0,
            "",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            1,
            "Débitos Fiscales",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            2,
            "Base Imponible",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            3,
            "Débito Fiscal",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            4,
            "Base Imponible",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            5,
            "Débito Fiscal",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            6,
            "Base Imponible",
            merge_format
        )
        worksheet.write(
            resume_row_init,
            7,
            "Débito Fiscal",
            merge_format
        )

        resume_book = self._resume_book_fields(row_total)

        for count, resume_row in enumerate(resume_book):
            number = count + 1
            row_resume = resume_row_init + number
            if number % 2 == 0:
                color = "b8cce4"
            else:
                color = "dbe5f1"

            dic_format_extend = {
                "fg_color": color,
                "border": 1,
                "num_format": "#,##0.00"
            }

            base_format = {
                "fg_color": color,
                "border": 1
            }

            format = workbook.add_format(dic_format_extend)
            format_base = workbook.add_format(base_format)

            worksheet.write(row_resume, 0, number, format_base)
            worksheet.write(row_resume, 1, resume_row["name"], format)
            worksheet.write(row_resume, 2, resume_row["fac_calc"], format)
            worksheet.write(row_resume, 3, resume_row["fac_debit_fiscal"], format)
            worksheet.write(row_resume, 4, resume_row["nc_calc"], format)
            worksheet.write(row_resume, 5, resume_row["nc_debit_fiscal"], format)
            worksheet.write(row_resume, 6, resume_row["tn_calc"], format)
            worksheet.write(row_resume, 7, resume_row["tn_debit_fiscal"], format)

        workbook.close()
        return file.getvalue()

    def _determinate_amount_taxeds(self, move):
        is_posted = move.state == "posted"

        if not is_posted:
            return {
                "amount_untaxed": 0.0,
                "amount_taxed": 0.0,
                "tax_base_8": 0.0,
                "tax_base_16": 0.0,
                "aliquot_8": 0.0,
                "aliquot_16": 0.0
            }

        is_credit_note = move.move_type == "out_refund"

        tax_totals = move.tax_totals

        tax_result = {}

        is_check_currency_system = self.currency_system

        if is_check_currency_system:
            fields_taxed = (
                "amount_untaxed",
                "amount_total",
                "groups_by_subtotal"
            )
        else:
            fields_taxed = (
                "foreign_amount_untaxed",
                "foreign_amount_total",
                "groups_by_foreign_subtotal"
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

        tax_result.update({
            "amount_untaxed": amount_untaxed,
            "amount_taxed": amount_taxed
        })

        tax_base = tax_totals.get(fields_taxed[2])

        for base in tax_base.items():
            taxes = base[1]

            for tax in taxes:
                tax_name = tax.get("tax_group_name")

                is_8 = tax_name == "IVA 8%"
                if is_8:
                    tax_result.update({
                        "tax_base_8": (
                            tax.get("tax_group_base_amount") * -1
                            if is_credit_note
                            else tax.get("tax_group_base_amount")
                        ),
                        "aliquot_8": (
                            tax.get("tax_group_amount") * -1
                            if is_credit_note
                            else tax.get("tax_group_amount")
                         )
                    })

                    continue

                is_16 = tax_name == "IVA 16%"
                if is_16:
                    tax_result.update({
                        "tax_base_16": (
                            tax.get("tax_group_base_amount") * -1
                            if is_credit_note
                            else tax.get("tax_group_base_amount")
                        ),
                        "aliquot_16": (
                            tax.get("tax_group_amount") * -1
                            if is_credit_note
                            else tax.get("tax_group_amount")
                        )
                    })

        return tax_result

    def generate_purchases_book(self):
        pass
