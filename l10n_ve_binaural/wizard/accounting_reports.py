import logging
from datetime import datetime
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta
from odoo import fields, models, _
from odoo.exceptions import UserError
from xlsxwriter import utility

_logger = logging.getLogger(__name__)
INIT_LINES = 8


class WizardAccountingReportsBinauralInvoice(models.TransientModel):
    _name = "wizard.accounting.reports"
    _description = "Wizard para generar reportes de libro de compra y ventas"
    _check_company_auto = True

    def _default_check_currency_system(self):
        is_system_currency_bs = self.env.company.currency_id.name == "VEF"
        return is_system_currency_bs

    def _default_date_to(self):
        current_day = fields.Date.today()
        return current_day

    def _default_date_from(self):
        current_day = self._default_date_to()
        final_day_month = relativedelta(months=-1)
        increment_date = current_day + final_day_month
        return increment_date

    def _default_company_id(self):
        company_id = self.env.company.id
        return company_id

    report = fields.Selection(
        [("purchase", "Book Purchase"), ("sale", "Sale Book")],
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
        if not move.invoice_date:
            raise UserError(_("Check the move %s does not have an invoice date and its id is %s", move.name, move.id))
        multiplier = -1 if move.move_type == "out_refund" else 1
        return {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date),
            "accounting_date": self._format_date(move.date),
            "vat": move.vat,
            "partner_name": move.invoice_partner_display_name,
            "document_number": move.name,
            "move_type": self._determinate_type(move.move_type),
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": move.reversed_entry_id.name or "--",
            "correlative": move.correlative,
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "total_sales_iva": taxes.get("amount_taxed", 0),
            "total_sales_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
        }

    def _fields_purchase_book_line(self, move, taxes):
        if not move.invoice_date:
            raise UserError(_("Check the move %s does not have an invoice date and its id is %s", move.name, move.id))
        multiplier = -1 if move.move_type == "in_refund" else 1
        fields_purchase_book_line = {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date),
            "accounting_date": self._format_date(move.date),
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
        if self.company_id.config_deductible_tax and self.report == "purchase":
            fields_purchase_book_line.update(
                {
                    "reduced_aliquot_no_deductible": 0.08,
                    "extend_aliquot_no_deductible": 0.31,
                    "general_aliquot_no_deductible": 0.16,
                    "amount_reduced_aliquot_no_deductible": taxes.get("amount_reduced_aliquot_no_deductible", 0) * multiplier,
                    "amount_general_aliquot_no_deductible": taxes.get("amount_general_aliquot_no_deductible", 0) * multiplier,
                    "amount_extend_aliquot_no_deductible": taxes.get("amount_extend_aliquot_no_deductible", 0) * multiplier,
                    "tax_base_reduced_aliquot_no_deductible": taxes.get("tax_base_reduced_aliquot_no_deductible", 0) * multiplier,
                    "tax_base_general_aliquot_no_deductible": taxes.get("tax_base_general_aliquot_no_deductible", 0) * multiplier,
                    "tax_base_extend_aliquot_no_deductible": taxes.get("tax_base_extend_aliquot_no_deductible", 0) * multiplier,
                }
            )
        return fields_purchase_book_line

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

        def check_future_dates(move):
            if move.date < self.date_from or move.date > self.date_to:
                return False
            return True

        def filter_credit_notes(move):
            types = ["out_refund", "in_refund"]
            return move.move_type in types

        moves = moves.filtered(check_future_dates)
        credit_notes = moves.filtered(filter_credit_notes)
        moves -= credit_notes

        if tax_type == "exempt_aliquot":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_exempt_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_exempt_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_exempt_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_exempt_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines
        if tax_type == "general_aliquot":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_general_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_general_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_general_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_general_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines
        if tax_type == "reduced_aliquot":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_reduced_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_reduced_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_reduced_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_reduced_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines
        if tax_type == "extend_aliquot":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_extend_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_extend_aliquot"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_extend_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_extend_aliquot"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines

        return [0.0, 0.0, 0.0, 0.0]

    def sale_book_fields(self):
        sale_fields = [
            {
                "name": "N° operacion",
                "field": "index",
            },
            {
                "name": "Fecha del documento",
                "field": "document_date",
                "size": 15,
            },
            {"name": "RIF", "field": "vat", "size": 15},
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
                "name": "N° de documento",
                "field": "document_number",
                "size": 20,
            },
            {
                "name": "Nª de Control",
                "field": "correlative",
            },
            {"name": "Tipo de Transacción", "field": "transaction_type"},
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
            
            
            
        ]

        if not self.company_id.not_show_reduced_aliquot_sale:
            fields_info = [
                ("Base imponible (8%)", "tax_base_reduced_aliquot", "number"),
                ("Alicuota (8%)", "reduced_aliquot", "percent"),
                ("IVA 8%", "amount_reduced_aliquot", "number")
            ]

            sale_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 15}
                for name, field, format_type in fields_info
            ])

        # if not self.company_id.not_show_extend_aliquot_sale:
            # fields_info = [
            #     ("Base imponible (31%)", "tax_base_extend_aliquot", "number"),
            #     ("Alicuota (31%)", "extend_aliquot", "percent"),
            #     ("IVA 31%", "amount_extend_aliquot", "number")
            # ]

            # sale_fields.extend([
            #     {"name": name, "field": field, "format": format_type, "size": 15}
            #     for name, field, format_type in fields_info
            # ])

        return sale_fields
    
    def purchase_book_fields(self):
        purchase_fields = [
            {
                "name": "N° operacion",
                "field": "index",
            },
            {
                "name": "Fecha del documento",
                "field": "document_date",
                "size": 15,
            },
            {"name": "RIF", "field": "vat", "size": 15},
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
                "name": "N° de documento",
                "field": "document_number",
                "size": 20,
            },
            {
                "name": "Nª de Control",
                "field": "correlative",
                "size": 15,
            },
            {"name": "Tipo de Transacción", "field": "transaction_type"},
            {
                "name": "NFactura Afectada",
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
        ]

        if not self.company_id.not_show_reduced_aliquot_purchase:
            fields_info = [
                ("Base imponible (8%)", "tax_base_reduced_aliquot", "number"),
                ("Alicuota (8%)", "reduced_aliquot", "percent"),
                ("IVA 8%", "amount_reduced_aliquot", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 15}
                for name, field, format_type in fields_info
            ])

        if not self.company_id.not_show_extend_aliquot_purchase:
            fields_info = [
                ("Base imponible (31%)", "tax_base_extend_aliquot", "number"),
                ("Alicuota (31%)", "extend_aliquot", "percent"),
                ("IVA 31%", "amount_extend_aliquot", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 15}
                for name, field, format_type in fields_info
            ])
        
        if self.company_id.config_deductible_tax:
            purchase_fields = self.not_deductible_purchase_book_fields(purchase_fields)

        return purchase_fields
    
    def not_deductible_purchase_book_fields(self, purchase_fields):
        
        if self.company_id.no_deductible_general_aliquot_purchase:
            fields_info = [
                ("Base imponible", "tax_base_general_aliquot_no_deductible", "number"),
                ("Alicuota (16%)", "general_aliquot_no_deductible", "percent"),
                ("Credito Fiscal No deducible (16%)", "amount_general_aliquot_no_deductible", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 15}
                for name, field, format_type in fields_info
            ])

        if self.company_id.no_deductible_reduced_aliquot_purchase:
            fields_info = [
                ("Base imponible", "tax_base_reduced_aliquot_no_deductible", "number"),
                ("Alicuota (8%)", "reduced_aliquot_no_deductible", "percent"),
                ("Credito Fiscal No deducible (8%)", "amount_reduced_aliquot_no_deductible", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 15}
                for name, field, format_type in fields_info
            ])

        if self.company_id.no_deductible_extend_aliquot_purchase:
            fields_info = [
                ("Base imponible", "tax_base_extend_aliquot_no_deductible", "number"),
                ("Alicuota (31%)", "extend_aliquot_no_deductible", "percent"),
                ("Credito Fiscal No deducible (31%)", "amount_extend_aliquot_no_deductible", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 15}
                for name, field, format_type in fields_info
            ])

        return purchase_fields

    def resume_book_headers(self):
        credit_or_debit_based_on_report_type = {"purchase": "Crédito", "sale": "Débito"}
        HEADERS = ("Base Imponible", f"{credit_or_debit_based_on_report_type[self.report]} Fiscal")

        return [
            {
                "name": "Resumen",
                "field": "resume",
                "headers": [
                    "",
                    f"{credit_or_debit_based_on_report_type[self.report]}s Fiscales",
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

    def _get_domain(self):
        search_domain = []
        is_purchase = self.report == "purchase"

        search_domain += [("company_id", "=", self.company_id.id)]

        move_type = (
            ["out_invoice", "out_refund"]
            if not is_purchase
            else ["in_invoice", "in_refund", "in_debit"]
        )

        search_domain += [("date", ">=", self.date_from)]
        search_domain += [("date", "<=", self.date_to)]
        search_domain += [
            ("state", "in", ("posted", "cancel")),
            ("move_type", "in", move_type),
            ("correlative", "not in", ['/',False])
        ]

        return search_domain

    def generate_report(self):
        is_sale = self.report == "sale"

        if is_sale:
            return self.download_sales_book()

        return self.download_purchases_book()

    def download_sales_book(self):
        self.ensure_one()
        url = "/web/download_sales_book?company_id=%s" % self.company_id.id
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def download_purchases_book(self):
        self.ensure_one()
        url = "/web/download_purchase_book?company_id=%s" % self.company_id.id
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
        order = "invoice_date asc" if self.report == "purchase" else "correlative asc"
        env = self.env
        move_model = env["account.move"]
        domain = self._get_domain()
        moves = move_model.search(domain, order=order)
        return moves

    def _resume_sale_book_fields(self, moves):
        return [
            {
                "name": "Ventas Internas no Gravadas",
                "format": "number",
                "values": self._determinate_resume_books(moves, "exempt_aliquot"),
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves),
            },
            {
                "name": "Exportaciones Gravadas por Alícuota General más Adicional",
                "format": "number",
                "values": self._determinate_resume_books(moves),
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
                "values": self._determinate_resume_books(moves),
            },
            {
                "name": "Total Ventas y Débitos Fiscales del Periodo",
                "format": "number",
                "values": self._determinate_resume_books(moves),
                "total": True,
            },
        ]

    def _resume_purchase_book_fields(self, moves):
        return [
            {
                "name": "Compras Internas no Gravadas",
                "format": "number",
                "values": self._determinate_resume_books(moves, "exempt_aliquot"),
            },
            {
                "name": "Importaciones Gravadas por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves),
            },
            {
                "name": "Importaciones Gravadas por Alícuota General más Adicional",
                "format": "number",
                "values": self._determinate_resume_books(moves),
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
                "values": self._determinate_resume_books(moves),
            },
            {
                "name": "Total Compras y Créditos Fiscales del Periodo",
                "format": "number",
                "values": self._determinate_resume_books(moves),
                "total": True,
            },
        ]

    def _determinate_amount_taxeds(self, move):
        is_posted = move.state == "posted"
        vef_base = self.company_id.currency_id.id == self.env.ref("base.VEF").id

        if not is_posted:
            fields_in_zero = {
                "amount_untaxed": 0.0,
                "amount_taxed": 0.0,
                "tax_base_exempt_aliquot": 0.0,
                "amount_exempt_aliquot": 0.0,
                "tax_base_reduced_aliquot": 0.0,
                "tax_base_general_aliquot": 0.0,
                "tax_base_extend_aliquot": 0.0,
                "amount_reduced_aliquot": 0.0,
                "amount_general_aliquot": 0.0,
                "amount_extend_aliquot": 0.0,
            }

            if self.company_id.config_deductible_tax and self.report == "purchase":
                fields_in_zero.update(
                    {
                        "tax_base_reduced_aliquot_no_deductible": 0.0,
                        "tax_base_general_aliquot_no_deductible": 0.0,
                        "tax_base_extend_aliquot_no_deductible": 0.0,
                        "amount_reduced_aliquot_no_deductible": 0.0,
                        "amount_general_aliquot_no_deductible": 0.0,
                        "amount_extend_aliquot_no_deductible": 0.0,
                    }
                )
            return fields_in_zero

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
        ) if tax_totals else 0

        amount_taxed = (
            tax_totals.get(fields_taxed[1]) * -1
            if is_credit_note and tax_totals.get(fields_taxed[1])
            else tax_totals.get(fields_taxed[1])
        ) if tax_totals else 0

        tax_result.update(
            {
                "amount_untaxed": amount_untaxed,
                "amount_taxed": amount_taxed,
                "tax_base_exempt_aliquot": 0,
                "amount_exempt_aliquot": 0,
                "tax_base_reduced_aliquot": 0,
                "amount_reduced_aliquot": 0,
                "tax_base_general_aliquot": 0,
                "amount_general_aliquot": 0,
                "tax_base_extend_aliquot": 0,
                "amount_extend_aliquot": 0,
            }
        )
        if not tax_totals:
            return tax_result

        if self.company_id.config_deductible_tax and self.report == "purchase":
            tax_result.update(
                {
                    "tax_base_reduced_aliquot_no_deductible": 0.0,
                    "tax_base_general_aliquot_no_deductible": 0.0,
                    "tax_base_extend_aliquot_no_deductible": 0.0,
                    "amount_reduced_aliquot_no_deductible": 0.0,
                    "amount_general_aliquot_no_deductible": 0.0,
                    "amount_extend_aliquot_no_deductible": 0.0,
                }
            )

        is_currency_system = (
            "groups_by_subtotal"
            if (vef_base and self.currency_system) or self.currency_system
            else "groups_by_foreign_subtotal"
        )
        tax_base = tax_totals.get(is_currency_system)

        for base in tax_base.items():
            taxes = base[1]

            exent_aliquot = False
            general_aliquot = False
            reduced_aliquot = False
            extend_aliquot = False

            if self.report == "sale":
                exent_aliquot = self.company_id.exent_aliquot_sale.tax_group_id.id
                reduced_aliquot = self.company_id.reduced_aliquot_sale.tax_group_id.id
                general_aliquot = self.company_id.general_aliquot_sale.tax_group_id.id
                extend_aliquot = self.company_id.extend_aliquot_sale.tax_group_id.id
            else:
                exent_aliquot = self.company_id.exent_aliquot_purchase.tax_group_id.id
                reduced_aliquot = self.company_id.reduced_aliquot_purchase.tax_group_id.id
                general_aliquot = self.company_id.general_aliquot_purchase.tax_group_id.id
                extend_aliquot = self.company_id.extend_aliquot_purchase.tax_group_id.id
                if self.company_id.config_deductible_tax:
                    general_aliquot_no_deductible = self.company_id.no_deductible_general_aliquot_purchase.tax_group_id.id
                    reduced_aliquot_no_deductible = self.company_id.no_deductible_reduced_aliquot_purchase.tax_group_id.id
                    extend_aliquot_no_deductible = self.company_id.no_deductible_extend_aliquot_purchase.tax_group_id.id

            for tax in taxes:
                tax_group_id = tax.get("tax_group_id")

                is_exempt = tax_group_id == exent_aliquot
                if is_exempt:
                    tax_result.update(
                        {
                            "tax_base_exempt_aliquot": tax.get("tax_group_base_amount"),
                            "amount_exempt_aliquot": tax.get("tax_group_amount"),
                        }
                    )

                is_reduced_aliquot = tax_group_id == reduced_aliquot
                if is_reduced_aliquot:
                    tax_result.update(
                        {
                            "tax_base_reduced_aliquot": tax.get("tax_group_base_amount"),
                            "amount_reduced_aliquot": tax.get("tax_group_amount"),
                        }
                    )

                    continue

                is_general_aliquot = tax_group_id == general_aliquot
                if is_general_aliquot:
                    tax_result.update(
                        {
                            "tax_base_general_aliquot": tax.get("tax_group_base_amount"),
                            "amount_general_aliquot": tax.get("tax_group_amount"),
                        }
                    )

                    continue

                is_extend_aliquot = tax_group_id == extend_aliquot
                if is_extend_aliquot:
                    tax_result.update(
                        {
                            "tax_base_extend_aliquot": tax.get("tax_group_base_amount"),
                            "amount_extend_aliquot": tax.get("tax_group_amount"),
                        }
                    )
                
                if self.company_id.config_deductible_tax and self.report == "purchase":

                    is_reduced_aliquot_no_deductible = tax_group_id == reduced_aliquot_no_deductible
                    if is_reduced_aliquot_no_deductible:
                        tax_result.update(
                            {
                                "tax_base_reduced_aliquot_no_deductible": tax.get("tax_group_base_amount"),
                                "amount_reduced_aliquot_no_deductible": tax.get("tax_group_amount"),
                            }
                        )

                        continue

                    is_general_aliquot_no_deductible = tax_group_id == general_aliquot_no_deductible
                    if is_general_aliquot_no_deductible:
                        tax_result.update(
                            {
                                "tax_base_general_aliquot_no_deductible": tax.get("tax_group_base_amount"),
                                "amount_general_aliquot_no_deductible": tax.get("tax_group_amount"),
                            }
                        )

                        continue

                    is_extend_aliquot_no_deductible = tax_group_id == extend_aliquot_no_deductible
                    if is_extend_aliquot_no_deductible:
                        tax_result.update(
                            {
                                "tax_base_extend_aliquot_no_deductible": tax.get("tax_group_base_amount"),
                                "amount_extend_aliquot_no_deductible": tax.get("tax_group_amount"),
                            }
                        )

        return tax_result

    def generate_sales_book(self, company_id):
        self.company_id = company_id
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

        # header
        worksheet.merge_range(
            "C1:M1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({"bold": True, "center_across": True, "font_size": 18}),
        )
        worksheet.merge_range(
            "C2:M2",
            f"Direccion:  {self.company_id.street}",
            cell_bold,
        )
        worksheet.merge_range("C3:M3", "Libro de Ventas", cell_bold)
        worksheet.merge_range(
            "C4:M4",
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
                    worksheet.write(
                        INIT_LINES + index_line, index, line.get(field["field"]), cell_format
                    )

            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}9:{col}{total_idx})", cell_formats.get("number")
                )

        self.generate_book_resume(worksheet, total_idx, merge_format, cell_formats)

        workbook.close()
        return file.getvalue()

    def generate_purchases_book(self, company_id):
        self.company_id = company_id
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

        # header
        worksheet.merge_range(
            "C1:M1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({"bold": True, "center_across": True, "font_size": 18}),
        ) 
        worksheet.merge_range(
            "C2:M2",
            f"Direccion:  {self.company_id.street}",
            cell_bold,
        )
        worksheet.merge_range("C3:M3", "Libro de Compras", cell_bold)
        worksheet.merge_range(
            "C4:M4",
            (
                f"Desde {self._format_date(self.date_from)}"
                f" Hasta {self._format_date(self.date_to)}"
            ),
            cell_bold,
        )

        company = self.company_id
        if self.company_id.config_deductible_tax:            
            row_buy_national = 3

            if company.not_show_reduced_aliquot_purchase or company.not_show_extend_aliquot_purchase:
                if company.not_show_reduced_aliquot_purchase != company.not_show_extend_aliquot_purchase:
                    row_buy_national -= 1
                else:
                    row_buy_national = 1

            ranges = {
                1: "L6:N6",
                2: "L6:Q6",
                3: "L6:T6",
            }

            buy_rows = ranges.get(row_buy_national, "")
            worksheet.merge_range(
                buy_rows, 
                "COMPRAS NACIONALES DEDUCIBLES", 
                merge_format
            )

            range_limit_n = len(
                company.no_deductible_general_aliquot_purchase +
                company.no_deductible_reduced_aliquot_purchase +
                company.no_deductible_extend_aliquot_purchase
            )
            if range_limit_n:
                ranges_init = {
                    1: "O6",
                    2: "R6",
                    3: "U6",
                }
                buy_rows_not_credit_init = ranges_init.get(row_buy_national, "")

                ranges_limit = {
                    3: {1: "W6", 2: "Z6", 3: "AC6"},
                    2: {1: "T6", 2: "W6", 3: "Z6"},
                    1: {1: "Q6", 2: "T6", 3: "W6"},
                }
                buy_rows_not_credit_limit = ranges_limit.get(row_buy_national, {}).get(range_limit_n, "")

                buy_rows_not_credit = f"{buy_rows_not_credit_init}:{buy_rows_not_credit_limit}"

                worksheet.merge_range(
                    buy_rows_not_credit,
                    (
                        "COMPRAS NACIONALES SIN DERECHO A CREDITO FISCAL"
                    ),
                    merge_format,
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
                    worksheet.write(
                        INIT_LINES + index_line, index, line.get(field["field"]), cell_format
                    )

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
        resume_columns = (
            self._resume_purchase_book_fields(moves)
            if is_purchase
            else self._resume_sale_book_fields(moves)
        )

        for idx, resume in enumerate(resume_columns):
            row_resume = (index_to_start + 4) + idx

            worksheet.write(row_resume, 0, idx + 1)
            worksheet.write(row_resume, 1, resume.get("name"))

            total_line = 0
            for idx_line, line in enumerate(resume.get("values")):
                total_line = idx_line + 2
                worksheet.write(row_resume, idx_line + 2, line, cell_formats.get("number"))

            if not is_purchase:
                if resume.get("total"):
                    total_c_formula = f"=SUM(C{index_to_start + 5}:C{row_resume})"
                    total_d_formula = f"=SUM(D{index_to_start + 5}:D{row_resume})"

                    worksheet.write_formula(
                        row_resume, 2, total_c_formula, cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 3, total_d_formula, cell_formats.get("number")
                    )

            else:
                if resume.get("total"):
                    total_c_formula = f"=SUM(C{index_to_start + 5}:C{row_resume})"
                    total_d_formula = f"=SUM(D{index_to_start + 5}:D{row_resume})"

                    worksheet.write_formula(
                        row_resume, 2, total_c_formula, cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 3, total_d_formula, cell_formats.get("number")
                    )

            column_bi_range = (
                f"C{row_resume + 1}:{utility.xl_col_to_name(total_line - 1)}{row_resume + 1}"
            )
            column_df_range = (
                f"D{row_resume + 1}:{utility.xl_col_to_name(total_line)}{row_resume + 1}"
            )
            imposed_formula = (
                f"=SUMPRODUCT(--({column_bi_range}), --(MOD(COLUMN({column_bi_range}), 2)=1))"
            )
            debit_formula = (
                f"=SUMPRODUCT(--({column_df_range}), --(MOD(COLUMN({column_df_range}), 2)=0))"
            )

            worksheet.write_formula(
                row_resume, total_line + 1, imposed_formula, cell_formats.get("number")
            )
            worksheet.write_formula(
                row_resume, total_line + 2, debit_formula, cell_formats.get("number")
            )
