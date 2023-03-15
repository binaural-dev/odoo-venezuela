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
        default=False
    )

    def parse_sale_book_data(self):
        sale_book_lines = []
        moves = self.search_moves()

        for count, move in enumerate(moves):
            taxes = self._determinate_amount_taxeds(move)

            sale_book_line = {
                "operation_number": count,
                "document_date": self._format_date(move.date),
                "vat": move.vat,
                "partner_name": move.invoice_partner_display_name,
                "document_number": move.name,
                "move_type": self._determinate_type(move.move_type),
                "transaction_type": self._determinate_transaction_type(move),
                "number_invoice_affected": move.reversed_entry_id.name,
                "correlative": move.correlative,
                "IVA8%": 0.08,
                "IVA16%": 0.16,
                "total_sales_iva": taxes.get("amount_taxed") or "",
                "total_sales_not_iva": taxes.get("amount_untaxed") or "",
                "aliquot_8": taxes.get("aliquot_8") or "",
                "aliquot_16": taxes.get("aliquot_16") or "",
                "tax_base_8": taxes.get("tax_base_8") or "",
                "tax_base_16": taxes.get("tax_base_16") or "",
            }

            sale_book_lines.append(sale_book_line)

        return sale_book_lines

    def sale_book_fields(self):
        return [
            "N° operacion",
            "Fecha del documento",
            "Nombre/Razón Social",
            "tipo",
            "RIF",
            "Nª de Control",
            "N° de documento",
            "N° Factura Afectada",
            "Total ventas con IVA",
            "Total ventas exentas",
            "IVA 16%",
            "IVA 8%",
            "Base imponible (8%)",
            "Base imponible (16%)",
            "Alicuota (8%)",
            "Alicuota (16%)",
            "Fecha Retencion",
            "N° Retencion",
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
            "out_invoice": "FAC",
            "out_refund": "NC"
        }

        return types[move_type]

    def _determinate_transaction_type(self, move):
        if move.move_type == "out_invoice" and move.state == "posted":
            return "01-REG"

        if move.move_type == "out_debit" and move.state == "posted":
            return "02-REG"

        if move.move_type == "out_refund" and move.state == "posted":
            return "03-REG"

        if move.move_type in ["out_refund", "out_debit", "out_invoice"] and move.state in ["cancel"]:
            return "03-ANU"

    def search_moves(self):
        env = self.env
        move_model = env['account.move']
        domain = self._get_domain()
        return move_model.search(domain)

    def generate_sales_book(self):
        sale_book_lines = self.parse_sale_book_data()
        file = BytesIO()

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
        init_col = 0
        init_row = 4

        for count, name in enumerate(name_columns):
            col = init_col + count
            worksheet.write(init_row, col, name, cell_bold)

        for count, line in enumerate(sale_book_lines):
            row = init_row + 1 + count
            col = init_col + count - 1

            for _, line in line.items():
                worksheet.write(row, col, line)
                col += 1

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

        tax_totals = move.tax_totals

        tax_result = {}

        amount_untaxed = tax_totals.get("amount_untaxed")
        amount_taxed = tax_totals.get("amount_total")

        tax_result.update({
            "amount_untaxed": amount_untaxed,
            "amount_taxed": amount_taxed
        })

        is_currency_system = "groups_by_subtotal" if self.currency_system else "groups_by_foreign_subtotal"

        tax_base = tax_totals.get(is_currency_system)

        for base in tax_base.items():
            taxes = base[1]

            for tax in taxes:
                tax_name = tax.get("tax_group_name")

                is_8 = tax_name == "IVA 8%"
                if is_8:
                    tax_result.update({
                        "tax_base_8": tax.get("tax_group_base_amount"),
                        "aliquot_8": tax.get("tax_group_amount")
                    })

                    continue

                is_16 = tax_name == "IVA 16%"
                if is_16:
                    tax_result.update({
                        "tax_base_16": tax.get("tax_group_base_amount"),
                        "aliquot_16": tax.get("tax_group_amount")
                    })

        return tax_result

    def generate_purchases_book(self):
        pass
