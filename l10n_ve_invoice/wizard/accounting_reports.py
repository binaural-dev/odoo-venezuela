import logging
from datetime import datetime
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta
from odoo import fields, models, _
from odoo.exceptions import UserError
from xlsxwriter import utility
import re

_logger = logging.getLogger(__name__)
INIT_LINES = 7


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

    def _default_currency_system(self):
        return True if self.env.company.currency_id.id == self.env.ref("base.VEF").id else False

    show_field_currency_system = fields.Boolean(string="Report in currency system", default=_default_check_currency_system)

    def _default_currency_system(self):
        return True if self.env.company.currency_id.id == self.env.ref("base.VEF").id else False

    show_field_currency_system = fields.Boolean(string="Report in currency system", default=_default_check_currency_system)

    currency_system = fields.Boolean(string="Report in currency system", default=_default_currency_system)

    def _fields_sale_book_line(self, move, taxes):
        if not move.invoice_date_display:
            raise UserError(_("Check the move %s does not have an invoice date and its id is %s", move.name, move.id))
        multiplier = -1 if move.move_type in ["out_refund", "in_refund"] else 1
        values =  {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date_display),
            "accounting_date": self._format_date(move.date),
            "vat": move.vat or '--',
            "partner_name": move.invoice_partner_display_name,
            "move_type": self._determinate_type_for_move(move),
            "invoice_number": move.name if self._determinate_type_for_move(move) == "FAC" else "--",
            "credit_note_number": move.name if self._determinate_type_for_move(move) == "NC" else "--",
            "debit_note_number": move.name if self._determinate_type_for_move(move) == "ND" else "--",
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": (
                move.debit_origin_id.name
                if move.journal_id.is_debit
                else move.reversed_entry_id.name or "--"
            ),
            "correlative": move.correlative or '--',
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "extend_aliquot": 0.31,
            "total_sales": taxes.get("amount_taxed", 0),
            "total_sales_iva": taxes.get("amount_taxed", 0) - (taxes.get("tax_base_exempt_aliquot", 0) * multiplier),
            "total_sales_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0)
            * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0)
            * multiplier,
            "amount_extend_aliquot": taxes.get("amount_extend_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0)
            * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0)
            * multiplier,
            "tax_base_extend_aliquot": taxes.get("tax_base_extend_aliquot", 0) * multiplier,
        }
        return values

    def _fields_purchase_book_line(self, move, taxes):
        if not move.invoice_date_display:
            raise UserError(_("Check the move %s does not have an invoice date and its id is %s", move.name, move.id))

        multiplier = -1 if move.move_type in ["out_refund", "in_refund"] else 1

        if move.journal_id.is_purchase_international :
            tax_keys_to_check = [
            
                "amount_reduced_aliquot_international", "amount_general_aliquot_international", "amount_extend_aliquot_international",
                "tax_base_reduced_aliquot_international", "tax_base_general_aliquot_international", "tax_base_extend_aliquot_international",
                "international_tax_base_exempt_aliquot", "international_amount_taxed"
            ]

            total_tax_value = sum(taxes.get(key, 0) for key in tax_keys_to_check)
            if total_tax_value == 0:
                return None
    

        amount_taxed = taxes.get("amount_taxed", 0) + taxes.get("international_amount_taxed", 0)
        tax_base_exempt_aliquot = taxes.get("tax_base_exempt_aliquot", 0) + taxes.get("international_tax_base_exempt_aliquot", 0)

        fields_purchase_book_line = {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date_display),
            "accounting_date": self._format_date(move.date),
            "vat": move.vat,
            "partner_name": move.invoice_partner_display_name,
            "move_type": self._determinate_type_for_move(move),
            "invoice_number": move.name if self._determinate_type_for_move(move) == "FAC" else "",
            "credit_note_number": move.name if self._determinate_type_for_move(move) == "NC" else "",
            "debit_note_number": move.name if self._determinate_type_for_move(move) == "ND" else "",
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": move.debit_origin_id.name if move.journal_id.is_debit else move.reversed_entry_id.name or "--",
            "correlative": move.correlative if not move.declaration_unique_of_customs else "-",
            "reduced_aliquot": 0.08,
            "extend_aliquot": 0.31,
            "general_aliquot": 0.16,
            "total_purchases": amount_taxed,
            "total_purchases_iva": amount_taxed - (tax_base_exempt_aliquot * multiplier),
            "total_purchases_not_iva": tax_base_exempt_aliquot * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            "amount_extend_aliquot": taxes.get("amount_extend_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
            "tax_base_extend_aliquot": taxes.get("tax_base_extend_aliquot", 0) * multiplier,
        }

        fields_purchase_book_line.update(
            {   
                "total_purchases_international": taxes.get("international_amount_taxed", 0),
                "total_purchases_iva_international": taxes.get("international_amount_taxed", 0) - (taxes.get("international_tax_base_exempt_aliquot", 0) * multiplier),
                "total_purchases_not_iva_international": taxes.get("international_tax_base_exempt_aliquot", 0) * multiplier,
                "amount_reduced_aliquot_international": taxes.get("amount_reduced_aliquot_international", 0) * multiplier,
                "amount_general_aliquot_international": taxes.get("amount_general_aliquot_international", 0) * multiplier,
                "amount_extend_aliquot_international": taxes.get("amount_extend_aliquot_international", 0) * multiplier,
                "tax_base_reduced_aliquot_international": taxes.get("tax_base_reduced_aliquot_international", 0) * multiplier,
                "tax_base_general_aliquot_international": taxes.get("tax_base_general_aliquot_international", 0) * multiplier,
                "tax_base_extend_aliquot_international": taxes.get("tax_base_extend_aliquot_international", 0) * multiplier,
                "declaration_unique_of_customs": move.declaration_unique_of_customs or "-",
                "amount_import_international": taxes.get("amount_import_international", 0),
                "import_file_number_purchase_international": move.import_file_number_purchase_international or "--",
            }
        )

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
            if purchase_book_line:
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
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_exempt_aliquot"]
                        for move in moves
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_exempt_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_exempt_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
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
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_general_aliquot"]
                        for move in moves
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_general_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_general_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
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
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_reduced_aliquot"]
                        for move in moves
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_reduced_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_reduced_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
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
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_extend_aliquot"]
                        for move in moves
                        if not move.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_extend_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_extend_aliquot"] * -1
                        for note in credit_notes
                        if not note.journal_id.is_purchase_international
                    ]
                )
            )
            return resume_lines


        if tax_type == "general_aliquot_international":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_general_aliquot_international"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_general_aliquot_international"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_general_aliquot_international"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_general_aliquot_international"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines

        if tax_type == "reduced_aliquot_international":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_reduced_aliquot_international"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_reduced_aliquot_international"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_reduced_aliquot_international"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_reduced_aliquot_international"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines

        if tax_type == "extend_aliquot_international":
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["tax_base_extend_aliquot_international"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(move)["amount_extend_aliquot_international"]
                        for move in moves
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["tax_base_extend_aliquot_international"] * -1
                        for note in credit_notes
                    ]
                )
            )
            resume_lines.append(
                sum(
                    [
                        self._determinate_amount_taxeds(note)["amount_extend_aliquot_international"] * -1
                        for note in credit_notes
                    ]
                )
            )

            return resume_lines

        return [0.0, 0.0, 0.0, 0.0]

    def sale_book_fields(self):
        sale_groups = self._get_sale_book_field_groups()
        flat_fields = []
        for group in sale_groups:
            flat_fields.extend(group['fields'])
     
        return flat_fields

    def purchase_book_fields(self):
        purchase_fields = [
            {
                "name": "N° operacion",
                "field": "index",
            },
            {
                "name": "Fecha del documento",
                "field": "document_date",
                "size": 16,
            },
            {"name": "RIF", "field": "vat", "size": 16},
            {
                "name": "Nombre/Razón social",
                "field": "partner_name",
                "size": 25,
            },
            {
                "name": "Tipo de Documento",
                "field": "move_type",
                "size": 16,
            },
            {
                "name": "N° de Factura",
                "field": "invoice_number",
                "size": 16,
            },
            {
                "name": "N° Nota de Crédito",
                "field": "credit_note_number",
                "size": 16,
            },
            {
                "name": "N° Nota de Débito",
                "field": "debit_note_number",
                "size": 16,
            },
            {
                "name": "N° de control",
                "field": "correlative",
                "size": 16,
            },
            {"name": "Tipo de transacción", "field": "transaction_type"},
            {
                "name": "N° Factura afectada",
                "field": "number_invoice_affected",
                "size": 16,
            },
            {
                "name": "Total compras con IVA",
                "field": "total_purchases_iva",
                "format": "number",
                "size": 16,
            },
            {
                "name": "Total compras exentas",
                "field": "total_purchases_not_iva",
                "format": "number",
                "size": 16,
            },
            {
                "name": "Base imponible (16%)",
                "field": "tax_base_general_aliquot",
                "format": "number",
                "size": 16,
            },
            {
                "name": "Alicuota (16%)",
                "field": "general_aliquot",
                "format": "percent",
                "size": 16,
            },
            {
                "name": "IVA 16%",
                "field": "amount_general_aliquot",
                "format": "number",
                "size": 16,
            },
        ]

        if not self.company_id.not_show_reduced_aliquot_purchase:
            fields_info = [
                ("Base imponible (8%)", "tax_base_reduced_aliquot", "number"),
                ("Alicuota (8%)", "reduced_aliquot", "percent"),
                ("IVA 8%", "amount_reduced_aliquot", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])

        if not self.company_id.not_show_extend_aliquot_purchase:
            fields_info = [
                ("Base imponible (31%)", "tax_base_extend_aliquot", "number"),
                ("Alicuota (31%)", "extend_aliquot", "percent"),
                ("IVA 31%", "amount_extend_aliquot", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])
        
        """ International Purchase Fields """
        
        if not self.company_id.not_show_general_aliquot_purchase_international:
            fields_info = [
                ("Base imponible (16%)", "tax_base_general_aliquot_international", "number"),
                ("Alicuota Int. (16%)", "general_aliquot", "percent"), 
                ("IVA Int. 16%", "amount_general_aliquot_international", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])

        if not self.company_id.not_show_reduced_aliquot_purchase_international:
            fields_info = [
                ("Base imponible (8%)", "tax_base_reduced_aliquot_international", "number"),
                ("Alicuota Int. (8%)", "reduced_aliquot", "percent"), 
                ("IVA Int. 8%", "amount_reduced_aliquot_international", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])

        if not self.company_id.not_show_extend_aliquot_purchase_international:
            fields_info = [
                ("Base imponible (31%)", "tax_base_extend_aliquot_international", "number"),
                ("Alicuota Int. (31%)", "extend_aliquot", "percent"), 
                ("IVA Int. 31%", "amount_extend_aliquot_international", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])

        """ Fin international purchase fields """
        
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
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])

        if self.company_id.no_deductible_reduced_aliquot_purchase:
            fields_info = [
                ("Base imponible", "tax_base_reduced_aliquot_no_deductible", "number"),
                ("Alicuota (8%)", "reduced_aliquot_no_deductible", "percent"),
                ("Credito Fiscal No deducible (8%)", "amount_reduced_aliquot_no_deductible", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
                for name, field, format_type in fields_info
            ])

        if self.company_id.no_deductible_extend_aliquot_purchase:
            fields_info = [
                ("Base imponible", "tax_base_extend_aliquot_no_deductible", "number"),
                ("Alicuota (31%)", "extend_aliquot_no_deductible", "percent"),
                ("Credito Fiscal No deducible (31%)", "amount_extend_aliquot_no_deductible", "number")
            ]

            purchase_fields.extend([
                {"name": name, "field": field, "format": format_type, "size": 16}
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

        all_sub_aliquots_hidden = [
            self.company_id.not_show_general_aliquot_purchase_international,
            self.company_id.not_show_reduced_aliquot_purchase_international,
            self.company_id.not_show_extend_aliquot_purchase_international,
            self.company_id.not_show_total_purchases_with_international_iva,
            self.company_id.not_show_exempt_total_purchases,
            self.company_id.not_show_total_purchases_international
        ]

        is_hidden_international = all(config == True for config in all_sub_aliquots_hidden)

        if is_purchase and is_hidden_international:
            search_domain += [("journal_id.is_purchase_international", "=", False)]


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

    def _determinate_type_for_move(self, move):
        move_type = move.move_type
        if move.journal_id.is_debit:
            move_type = "in_debit"

        type_for_move = self._determinate_type(move_type)

        return type_for_move


    def _determinate_type(self, type):

        types = {
            "out_debit": "ND",
            "in_debit": "ND",
            "out_invoice": "FAC",
            "in_invoice": "FAC",
            "out_refund": "NC",
            "in_refund": "NC",
        }
        return types[type]

    def _determinate_transaction_type(self, move):
        if move.move_type in ["out_invoice", "in_invoice"] and move.state == "posted":
            if move.journal_id.is_debit:
                return "02-REG"
            else:
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
        order = "invoice_date_display asc" if self.report == "purchase" else "correlative asc"
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
                "name": "Importaciones Gravadas por Alícuota Reducida",
                "format": "number",
                "values": self._determinate_resume_books(moves, "reduced_aliquot_international"),
            },
            {
                "name": "Importaciones Gravadas por Alícuota General",
                "format": "number",
                "values": self._determinate_resume_books(moves, "general_aliquot_international"),
            },
            {
                "name": "Importaciones Gravadas por Alícuota General más Adicional",
                "format": "number",
                "values": self._determinate_resume_books(moves, "extend_aliquot_international"),
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
    
    def convert_currency_to_float(self, currency_str):
  
        if not currency_str:
            return 0.0
        
        cleaned_str = str(currency_str).strip()
       
        if '\xa0' in cleaned_str:
            cleaned_str = cleaned_str.split('\xa0', 1)[0]
        
        numeric_part = re.sub(r'[^\d,\.-]', '', cleaned_str)
        
        if '.' in numeric_part and ',' in numeric_part:
            numeric_part = numeric_part.replace('.', '')
        
        final_value = numeric_part.replace(',', '.')

        try:
            return float(final_value)
        except ValueError:
            _logger.warning(
                "No se pudo convertir la cadena de moneda '%s' a float. Valor final procesado: '%s'",
                currency_str,
                final_value
            )
            return 0.0

    def _determinate_amount_taxeds(self, move):
        is_posted = move.state == "posted"

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
                "international_amount_taxed": 0.0,
                "amount_import_international": 0,
                "international_tax_base_exempt_aliquot": 0.0,
                "tax_base_reduced_aliquot_international": 0,
                "amount_reduced_aliquot_international": 0,
                "tax_base_general_aliquot_international": 0,
                "amount_general_aliquot_international": 0,
                "tax_base_extend_aliquot_international": 0,
                "amount_extend_aliquot_international": 0,
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

        amount_untaxed = 0.0
        amount_taxed = 0.0
        tax_base_exempt_aliquot = 0.0
        amount_exempt_aliquot = 0.0
        tax_base_reduced_aliquot = 0.0
        amount_reduced_aliquot = 0.0
        tax_base_general_aliquot = 0.0
        amount_general_aliquot = 0.0
        tax_base_extend_aliquot = 0.0
        amount_extend_aliquot = 0.0

        base_key = "formatted_base_amount_currency_ves"
        tax_key = "formatted_tax_amount_currency_ves"

        # Sumar totales generales
        if tax_totals:
            amount_untaxed = self.convert_currency_to_float(tax_totals.get(base_key, ''))
            amount_taxed = self.convert_currency_to_float(tax_totals.get(tax_key, ''))
            if is_credit_note:
                amount_untaxed *= -1
                amount_taxed *= -1


        # Obtener los IDs de los grupos de impuestos desde la configuración de la compañía
        exent_aliquot_id = reduced_aliquot_id = general_aliquot_id = extend_aliquot_id = None
        reduced_aliquot_no_deductible_id = general_aliquot_no_deductible_id = extend_aliquot_no_deductible_id = None
        if self.report == "sale":
            if hasattr(self.company_id, "exent_aliquot_sale") and self.company_id.exent_aliquot_sale:
                exent_aliquot_id = getattr(self.company_id.exent_aliquot_sale.tax_group_id, "id", None)
            if hasattr(self.company_id, "reduced_aliquot_sale") and self.company_id.reduced_aliquot_sale:
                reduced_aliquot_id = getattr(self.company_id.reduced_aliquot_sale.tax_group_id, "id", None)
            if hasattr(self.company_id, "general_aliquot_sale") and self.company_id.general_aliquot_sale:
                general_aliquot_id = getattr(self.company_id.general_aliquot_sale.tax_group_id, "id", None)
            if hasattr(self.company_id, "extend_aliquot_sale") and self.company_id.extend_aliquot_sale:
                extend_aliquot_id = getattr(self.company_id.extend_aliquot_sale.tax_group_id, "id", None)
        else:
            if move.journal_id.is_purchase_international:
                if hasattr(self.company_id, "exent_aliquot_purchase_international") and self.company_id.exent_aliquot_purchase_international:
                    exent_aliquot_id = getattr(self.company_id.exent_aliquot_purchase_international.tax_group_id, "id", None)
                
                if not self.company_id.not_show_general_aliquot_purchase_international:
                    if hasattr(self.company_id, "general_aliquot_purchase_international") and self.company_id.general_aliquot_purchase_international:
                        general_aliquot_id = getattr(self.company_id.general_aliquot_purchase_international.tax_group_id, "id", None)
                
                if not self.company_id.not_show_reduced_aliquot_purchase_international:
                    if hasattr(self.company_id, "reduced_aliquot_purchase_international") and self.company_id.reduced_aliquot_purchase_international:
                        reduced_aliquot_id = getattr(self.company_id.reduced_aliquot_purchase_international.tax_group_id, "id", None)
                
                if not self.company_id.not_show_extend_aliquot_purchase_international:
                    if hasattr(self.company_id, "extend_aliquot_purchase_international") and self.company_id.extend_aliquot_purchase_international:
                        extend_aliquot_id = getattr(self.company_id.extend_aliquot_purchase_international.tax_group_id, "id", None)
            else:
                if hasattr(self.company_id, "exent_aliquot_purchase") and self.company_id.exent_aliquot_purchase:
                    exent_aliquot_id = getattr(self.company_id.exent_aliquot_purchase.tax_group_id, "id", None)
                if hasattr(self.company_id, "reduced_aliquot_purchase") and self.company_id.reduced_aliquot_purchase:
                    reduced_aliquot_id = getattr(self.company_id.reduced_aliquot_purchase.tax_group_id, "id", None)
                if hasattr(self.company_id, "general_aliquot_purchase") and self.company_id.general_aliquot_purchase:
                    general_aliquot_id = getattr(self.company_id.general_aliquot_purchase.tax_group_id, "id", None)
                if hasattr(self.company_id, "extend_aliquot_purchase") and self.company_id.extend_aliquot_purchase:
                    extend_aliquot_id = getattr(self.company_id.extend_aliquot_purchase.tax_group_id, "id", None)

            if self.company_id.config_deductible_tax:
                if hasattr(self.company_id, "no_deductible_general_aliquot_purchase") and self.company_id.no_deductible_general_aliquot_purchase:
                    general_aliquot_no_deductible_id = getattr(self.company_id.no_deductible_general_aliquot_purchase.tax_group_id, "id", None)
                if hasattr(self.company_id, "no_deductible_reduced_aliquot_purchase") and self.company_id.no_deductible_reduced_aliquot_purchase:
                    reduced_aliquot_no_deductible_id = getattr(self.company_id.no_deductible_reduced_aliquot_purchase.tax_group_id, "id", None)
                if hasattr(self.company_id, "no_deductible_extend_aliquot_purchase") and self.company_id.no_deductible_extend_aliquot_purchase:
                    extend_aliquot_no_deductible_id = getattr(self.company_id.no_deductible_extend_aliquot_purchase.tax_group_id, "id", None)

        # Procesar subtotals y tax_groups
        if tax_totals and tax_totals.get("subtotals"):
            for subtotal in tax_totals["subtotals"]:
                for group in subtotal.get("tax_groups", []):
                    group_id = group.get("id")
                    base = self.convert_currency_to_float(group.get(base_key,''))
                    tax = self.convert_currency_to_float(group.get(tax_key,''))
                    if is_credit_note:
                        base *= -1
                        tax *= -1
                    # Identificar por ID o si el impuesto es cero (asumiendo exento si no hay config)
                    is_exempt = (group_id and group_id == exent_aliquot_id) or (not exent_aliquot_id and tax == 0.0)
                    
                    if is_exempt:
                        tax_base_exempt_aliquot += base
                        amount_exempt_aliquot += tax
                        if move.journal_id.is_purchase_international:
                            tax_result["international_tax_base_exempt_aliquot"] = tax_result.get("international_tax_base_exempt_aliquot", 0.0) + base
                    elif group_id and group_id == reduced_aliquot_id:
                        tax_base_reduced_aliquot += base
                        amount_reduced_aliquot += tax
                    elif group_id and group_id == general_aliquot_id:
                        tax_base_general_aliquot += base
                        amount_general_aliquot += tax
                    elif group_id and group_id == extend_aliquot_id:
                        tax_base_extend_aliquot += base
                        amount_extend_aliquot += tax
                    # No deducibles
                    if self.company_id.config_deductible_tax and self.report == "purchase":
                        if group_id and group_id == reduced_aliquot_no_deductible_id:
                            tax_result["tax_base_reduced_aliquot_no_deductible"] = tax_result.get("tax_base_reduced_aliquot_no_deductible", 0.0) + base
                            tax_result["amount_reduced_aliquot_no_deductible"] = tax_result.get("amount_reduced_aliquot_no_deductible", 0.0) + tax
                        elif group_id and group_id == general_aliquot_no_deductible_id:
                            tax_result["tax_base_general_aliquot_no_deductible"] = tax_result.get("tax_base_general_aliquot_no_deductible", 0.0) + base
                            tax_result["amount_general_aliquot_no_deductible"] = tax_result.get("amount_general_aliquot_no_deductible", 0.0) + tax
                        elif group_id and group_id == extend_aliquot_no_deductible_id:
                            tax_result["tax_base_extend_aliquot_no_deductible"] = tax_result.get("tax_base_extend_aliquot_no_deductible", 0.0) + base
                            tax_result["amount_extend_aliquot_no_deductible"] = tax_result.get("amount_extend_aliquot_no_deductible", 0.0) + tax

        tax_result.update({
            "amount_untaxed": (
                tax_base_exempt_aliquot + tax_base_reduced_aliquot + 
                tax_base_general_aliquot + tax_base_extend_aliquot
            ),
            "amount_taxed": (
                tax_base_exempt_aliquot + tax_base_reduced_aliquot + 
                tax_base_general_aliquot + tax_base_extend_aliquot +
                amount_exempt_aliquot + amount_reduced_aliquot + 
                amount_general_aliquot + amount_extend_aliquot
            ),
            "tax_base_exempt_aliquot": tax_base_exempt_aliquot,
            "amount_exempt_aliquot": amount_exempt_aliquot,
            "tax_base_reduced_aliquot": tax_base_reduced_aliquot,
            "amount_reduced_aliquot": amount_reduced_aliquot,
            "tax_base_general_aliquot": tax_base_general_aliquot,
            "amount_general_aliquot": amount_general_aliquot,
            "tax_base_extend_aliquot": tax_base_extend_aliquot,
            "amount_extend_aliquot": amount_extend_aliquot,
            "tax_base_reduced_aliquot_international": 0.0,
            "amount_reduced_aliquot_international": 0.0,
            "tax_base_general_aliquot_international": 0.0,
            "amount_general_aliquot_international": 0.0,
            "tax_base_extend_aliquot_international": 0.0,
            "amount_extend_aliquot_international": 0.0,
            "international_tax_base_exempt_aliquot": tax_result.get("international_tax_base_exempt_aliquot", 0.0),
            "international_amount_taxed": 0.0,
        })

        if move.journal_id.is_purchase_international:
            # Use custom fields if available, otherwise use calculated taxes for GENERAL (16%)
            tb_general_intl = move.tax_base_for_international_purchase or tax_base_general_aliquot
            am_general_intl = move.tax_amount_for_international_purchase or amount_general_aliquot

            tax_result.update({
                "tax_base_reduced_aliquot_international": tax_base_reduced_aliquot,
                "amount_reduced_aliquot_international": amount_reduced_aliquot,
                "tax_base_general_aliquot_international": tb_general_intl,
                "amount_general_aliquot_international": am_general_intl,
                "tax_base_extend_aliquot_international": tax_base_extend_aliquot,
                "amount_extend_aliquot_international": amount_extend_aliquot,
                "international_tax_base_exempt_aliquot": tax_result.get("international_tax_base_exempt_aliquot", 0.0),
                "international_amount_taxed": (
                    tax_base_reduced_aliquot + amount_reduced_aliquot +
                    tb_general_intl + am_general_intl +
                    tax_base_extend_aliquot + amount_extend_aliquot +
                    tax_result.get("international_tax_base_exempt_aliquot", 0.0)
                ),
             })
            tax_result.update({
                "tax_base_reduced_aliquot": 0.0,
                "amount_reduced_aliquot": 0.0,
                "tax_base_general_aliquot": 0.0,
                "amount_general_aliquot": 0.0,
                "tax_base_extend_aliquot": 0.0,
                "amount_extend_aliquot": 0.0,
                "tax_base_exempt_aliquot": 0.0,
                "amount_exempt_aliquot": 0.0,
                "amount_taxed": 0.0,
                "amount_untaxed": 0.0,
                "tax_base_reduced_aliquot_no_deductible": 0.0,
                "tax_base_general_aliquot_no_deductible": 0.0,
                "tax_base_extend_aliquot_no_deductible": 0.0,
                "amount_reduced_aliquot_no_deductible": 0.0,
                "amount_general_aliquot_no_deductible": 0.0,
                "amount_extend_aliquot_no_deductible": 0.0,
            })

        # Inicializar en cero los campos no deducibles si no se asignaron
        if self.company_id.config_deductible_tax and self.report == "purchase":
            for k in [
                "tax_base_reduced_aliquot_no_deductible",
                "tax_base_general_aliquot_no_deductible",
                "tax_base_extend_aliquot_no_deductible",
                "amount_reduced_aliquot_no_deductible",
                "amount_general_aliquot_no_deductible",
                "amount_extend_aliquot_no_deductible",
            ]:
                tax_result.setdefault(k, 0.0)

        amount_import_international = 0.0
        if move.journal_id.is_purchase_international:
            amount_import_international = (
                tax_result.get("international_tax_base_exempt_aliquot", 0.0) +
                tax_result.get("tax_base_general_aliquot_international", 0.0) + tax_result.get("amount_general_aliquot_international", 0.0) +
                tax_result.get("tax_base_reduced_aliquot_international", 0.0) + tax_result.get("amount_reduced_aliquot_international", 0.0) +
                tax_result.get("tax_base_extend_aliquot_international", 0.0) + tax_result.get("amount_extend_aliquot_international", 0.0)
            )

        tax_result['amount_import_international'] = amount_import_international

        return tax_result

    def generate_sales_book(self, company_id):

        self.company_id = company_id
        sale_book_lines = self.parse_sale_book_data()
        file = BytesIO()

        password_protection = "secure"
        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
        worksheet = workbook.add_worksheet()

        cell_bold = workbook.add_format(
            {"bold": True, "center_across": True, "text_wrap": True, "bottom": True, "locked": True}
        )
        
        base_style = {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "locked": True}
        format1 = workbook.add_format(base_style); format1.set_bg_color('#D9D9D9')
        format2 = workbook.add_format(base_style); format2.set_bg_color('#F4B183')
        format3 = workbook.add_format(base_style); format3.set_bg_color('#A9D18E')
        format4 = workbook.add_format(base_style); format4.set_bg_color('#8FAADC')

        color_formats = [format1, format1, format2, format3, format4] 
        
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00", "locked": True}),
            "percent": workbook.add_format({"num_format": "0.00%", "locked": True}),
        }

        worksheet.merge_range(
            "C1:M1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({"bold": True, "center_across": True, "font_size": 18, "locked": True}),
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

        sale_groups = self._get_sale_book_field_groups()
        flat_fields = []
        current_col_index = 0
        color_index = 0 
        last_col_index = 0 

        for group in sale_groups:
            group_fields = group['fields']
            if not group_fields:
                continue

            header_format = color_formats[color_index % len(color_formats)]
            
            start_col = current_col_index
            num_fields = len(group_fields)
            end_col = start_col + num_fields - 1

            start_col_name = utility.xl_col_to_name(start_col)
            end_col_name = utility.xl_col_to_name(end_col)
            merge_range = f"{start_col_name}6:{end_col_name}6"

            worksheet.merge_range(
                merge_range, 
                group['header'], 
                header_format
            )
            
            for field in group_fields:
                col_index = current_col_index
                
                worksheet.write(6, col_index, field.get("name"), header_format) 
                
                worksheet.set_column(col_index, col_index, 25)
                flat_fields.append(field)
                
                current_col_index += 1
            
            color_index += 1 
        
        last_col_index = current_col_index - 1 
                
        name_columns = flat_fields 
        total_idx = 0

        for index, field in enumerate(name_columns):
            
            for index_line, line in enumerate(sale_book_lines):
                total_idx = (8 + index_line)
                if field["field"] == "index":
                    worksheet.write(INIT_LINES + index_line, index, index_line + 1)
                else:
                    cell_format = cell_formats.get(field.get("format"), workbook.add_format({"locked": True}))
                    worksheet.write(
                        INIT_LINES + index_line, index, line.get(field["field"]), cell_format
                    )

            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}8:{col}{total_idx})", cell_formats.get("number")
                )
        
        
        merge_format_base = workbook.add_format(
            {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "gray", "locked": True}
        )
        self.generate_book_resume(worksheet, total_idx, merge_format_base, cell_formats, last_col_index)
        
        worksheet.protect(password=password_protection)

        workbook.close()
        return file.getvalue()
        
    def purchase_book_fields(self):
        purchase_groups = self._get_purchase_book_field_groups()
        flat_fields = []
        for group in purchase_groups:
            flat_fields.extend(group['fields'])
     
        return flat_fields

    def generate_purchases_book(self, company_id):
        self.company_id = company_id
        purchase_book_lines = self.parse_purchase_book_data()
        file = BytesIO()

        password_protection = "secure"
        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True,"constant_memory": False})
        workbook.set_calc_mode('auto') 
        worksheet = workbook.add_worksheet()

        cell_bold = workbook.add_format(
            {"bold": True, "center_across": True, "text_wrap": True, "bottom": True, "locked": True}
        )

        merge_format = workbook.add_format(
            {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "locked": True}
        )
        merge_format.set_bg_color('#D9D9D9') 
        
        base_style = {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "locked": True}

        format1 = workbook.add_format(base_style); format1.set_bg_color('#D9D9D9')
        format2 = workbook.add_format(base_style); format2.set_bg_color('#C6E0B4')
        format3 = workbook.add_format(base_style); format3.set_bg_color('#FFE699')
        format4 = workbook.add_format(base_style); format4.set_bg_color('#B4C6E7')

        color_formats = [format1, format1, format2, format3, format4, format4] 
        
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00","locked": True}),
            "percent": workbook.add_format({"num_format": "0.00%", "locked": True}),
        }

        worksheet.merge_range(
            "C1:M1",
            f"{self.company_id.name} - {self.company_id.vat}",
            workbook.add_format({"bold": True, "center_across": True, "font_size": 18, "locked": True}),
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
        
        purchase_groups = self._get_purchase_book_field_groups()
        flat_fields = []
        current_col_index = 0
        color_index = 0 
        last_col_index = 0 
        for group in purchase_groups:
            group_fields = group['fields']
            if not group_fields:
                continue

            header_format = color_formats[color_index % len(color_formats)]
            
            start_col = current_col_index
            num_fields = len(group_fields)
            end_col = start_col + num_fields - 1

            start_col_name = utility.xl_col_to_name(start_col)
            end_col_name = utility.xl_col_to_name(end_col)
            merge_range = f"{start_col_name}6:{end_col_name}6"

            worksheet.merge_range(
                merge_range, 
                group['header'], 
                header_format
            )
            
            for field in group_fields:
                col_index = current_col_index
                
                worksheet.write(6, col_index, field.get("name"), header_format) 
                
                worksheet.set_column(col_index, col_index, 25)
                flat_fields.append(field)
                
                current_col_index += 1
            
            color_index += 1 
        
        last_col_index = current_col_index - 1
                
        name_columns = flat_fields 
        total_idx = 0

        for index, field in enumerate(name_columns):
            
            for index_line, line in enumerate(purchase_book_lines):
                total_idx = (8 + index_line)
                if field["field"] == "index":
                    worksheet.write(INIT_LINES + index_line, index, index_line + 1)
                else:
                    cell_format = cell_formats.get(field.get("format"), workbook.add_format({"locked": True}))
                    worksheet.write(
                        INIT_LINES + index_line, index, line.get(field["field"]), cell_format
                    )

            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                total_idx, index, f"=SUM({col}8:{col}{total_idx})", cell_formats.get("number")
            )
        
        self.generate_book_resume(worksheet, total_idx, merge_format, cell_formats, last_col_index)
        
        worksheet.protect(password=password_protection)

        workbook.close()
        return file.getvalue()
        
    def generate_book_resume(self, worksheet, index_to_start, merge_format, cell_formats,last_col_index=5):
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
        if not moves:
            raise UserError(_('There are no moves to show'))
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
                    total_e_formula = f"=SUM(E{index_to_start + 5}:E{row_resume})"
                    total_f_formula = f"=SUM(F{index_to_start + 5}:F{row_resume})"

                    worksheet.write_formula(
                        row_resume, 2, total_c_formula, cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 3, total_d_formula, cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 4, total_e_formula,cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 5, total_f_formula,cell_formats.get("number")
                    )

            else:
                if resume.get("total"):
                    total_c_formula = f"=SUM(C{index_to_start + 5}:C{row_resume})"
                    total_d_formula = f"=SUM(D{index_to_start + 5}:D{row_resume})"
                    total_e_formula = f"=SUM(E{index_to_start + 5}:E{row_resume})"
                    total_f_formula = f"=SUM(F{index_to_start + 5}:F{row_resume})"

                    worksheet.write_formula(
                        row_resume, 2, total_c_formula, cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 3, total_d_formula, cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 4, total_e_formula,cell_formats.get("number")
                    )
                    worksheet.write_formula(
                        row_resume, 5, total_f_formula,cell_formats.get("number")
                    )

            start_col_formula = 6
                
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
                row_resume, start_col_formula, imposed_formula, cell_formats.get("number")
            )
            worksheet.write_formula(
                row_resume, start_col_formula + 1, debit_formula, cell_formats.get("number")
                    )

    def _get_sale_book_field_groups(self):
        company = self.company_id
        sale_groups = []

        basic_fields = [
            {"name": "N° operacion", "field": "index",},
            {"name": "Fecha del documento", "field": "document_date", "size": 16},
            {"name": "RIF", "field": "vat", "size": 16},
            {"name": "Nombre/Razón social", "field": "partner_name", "size": None},
            {"name": "Tipo de Documento", "field": "move_type", "size": 16},
            {"name": "N° de Factura", "field": "invoice_number", "size": 16},
            {"name": "N° Nota de Crédito", "field": "credit_note_number", "size": 16},
            {"name": "N° Nota de Débito", "field": "debit_note_number", "size": 16},
            {"name": "N° de control", "field": "correlative", "size": 16},
            {"name": "Tipo de transacción", "field": "transaction_type"},
            {"name": "N° Factura afectada", "field": "number_invoice_affected", "size": 16},
        ]
        sale_groups.append({'header': 'DETALLE DEL DOCUMENTO', 'fields': basic_fields})

        total_fields = [
            {"name": "Total ventas", "field": "total_sales", "format": "number", "size": 16},
            {"name": "Total ventas con IVA", "field": "total_sales_iva", "format": "number", "size": 16},
            {"name": "Total ventas exentas", "field": "total_sales_not_iva", "format": "number", "size": 16},
        ]
        sale_groups.append({'header': 'TOTALES', 'fields': total_fields})

        general_aliquot_fields = [
            {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot", "format": "number", "size": 16},
            {"name": "Alicuota (16%)", "field": "general_aliquot", "format": "percent", "size": 16},
            {"name": "IVA 16%", "field": "amount_general_aliquot", "format": "number", "size": 16},
        ]
        sale_groups.append({'header': 'ALÍCUOTA GENERAL (16%)', 'fields': general_aliquot_fields})
        
        reduced_aliquot_fields = []
        if not company.not_show_reduced_aliquot_sale:
            reduced_aliquot_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot", "format": "number"},
                {"name": "Alicuota (8%)", "field": "reduced_aliquot", "format": "percent"},
                {"name": "IVA 8%", "field": "amount_reduced_aliquot", "format": "number"}
            ])

        if reduced_aliquot_fields:
            sale_groups.append({'header': 'ALÍCUOTA REDUCIDA (8%)', 'fields': reduced_aliquot_fields})

        extend_aliquot_fields = []
        if not company.not_show_extend_aliquot_sale:
            extend_aliquot_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot", "format": "number"},
                {"name": "Alicuota (31%)", "field": "extend_aliquot", "format": "percent"},
                {"name": "IVA 31%", "field": "amount_extend_aliquot", "format": "number"}
            ])
            
        if extend_aliquot_fields:
            sale_groups.append({'header': 'ALÍCUOTA ADICIONAL (31%)', 'fields': extend_aliquot_fields})

        return sale_groups
    

    def _get_purchase_book_field_groups(self):
        company = self.company_id
        purchase_groups = []

        basic_fields = [
            {"name": "N° operacion", "field": "index",},
            {"name": "Fecha del documento", "field": "document_date", "size": 16},
            {"name": "RIF", "field": "vat", "size": 16},
            {"name": "Nombre/Razón social", "field": "partner_name", "size": None},
            {"name": "Tipo de Documento", "field": "move_type", "size": 16},
            {"name": "N° de Factura", "field": "invoice_number", "size": 16},
            {"name": "N° Nota de Crédito", "field": "credit_note_number", "size": 16},
            {"name": "N° Nota de Débito", "field": "debit_note_number", "size": 16},
            {"name": "N° de control", "field": "correlative", "size": 16},
            {"name": "Tipo de transacción", "field": "transaction_type"},
            {"name": "N° Factura afectada", "field": "number_invoice_affected", "size": 16},
        ]
        purchase_groups.append({'header': 'DETALLE DEL DOCUMENTO', 'fields': basic_fields})

        total_fields = [
            {"name": "Total compras", "field": "total_purchases", "format": "number", "size": 16},
            {"name": "Total compras con IVA", "field": "total_purchases_iva", "format": "number", "size": 16},
            {"name": "Total compras exentas", "field": "total_purchases_not_iva", "format": "number", "size": 16},
        ]
        purchase_groups.append({'header': 'TOTALES', 'fields': total_fields})

        national_deductible_fields = []
       
        national_deductible_fields.extend([
            {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot", "format": "number", "size": 16},
            {"name": "Alicuota (16%)", "field": "general_aliquot", "format": "percent", "size": 16},
            {"name": "IVA 16%", "field": "amount_general_aliquot", "format": "number", "size": 16},
        ])
            
        if not company.not_show_reduced_aliquot_purchase:
            national_deductible_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot", "format": "number"},
                {"name": "Alicuota (8%)", "field": "reduced_aliquot", "format": "percent"},
                {"name": "IVA 8%", "field": "amount_reduced_aliquot", "format": "number"}
            ])

        if not company.not_show_extend_aliquot_purchase:
            national_deductible_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot", "format": "number"},
                {"name": "Alicuota (31%)", "field": "extend_aliquot", "format": "percent"},
                {"name": "IVA 31%", "field": "amount_extend_aliquot", "format": "number"}
            ])

        if national_deductible_fields:
            purchase_groups.append({'header': 'COMPRAS NACIONALES', 'fields': national_deductible_fields})

        international_fields = []
        if not company.not_show_general_aliquot_purchase_international:
            international_fields.extend([
                {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot_international", "format": "number"},
                {"name": "Alicuota Int. (16%)", "field": "general_aliquot", "format": "percent"},
                {"name": "IVA Int. 16%", "field": "amount_general_aliquot_international", "format": "number"}
            ])

        if not company.not_show_reduced_aliquot_purchase_international:
            international_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot_international", "format": "number"},
                {"name": "Alicuota Int. (8%)", "field": "reduced_aliquot", "format": "percent"},
                {"name": "IVA Int. 8%", "field": "amount_reduced_aliquot_international", "format": "number"}
            ])

        if not company.not_show_extend_aliquot_purchase_international:
            international_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot_international", "format": "number"},
                {"name": "Alicuota Int. (31%)", "field": "extend_aliquot", "format": "percent"},
                {"name": "IVA Int. 31%", "field": "amount_extend_aliquot_international", "format": "number"}
            ])
        
        international_total_fields = [
        ]

        if not company.not_show_total_purchases_international:
            international_total_fields.append(            
                {"name": "Total compras", "field": "total_purchases_international", "format": "number"},
            )

        if not company.not_show_total_purchases_with_international_iva:
            international_total_fields.append(            
                {"name": "Total compras con IVA", "field": "total_purchases_iva_international", "format": "number"},
            )

        if not company.not_show_exempt_total_purchases:
            international_total_fields.append(            
                {"name": "Total compras exentas", "field": "total_purchases_not_iva_international", "format": "number"},
            )

        if international_total_fields:
            purchase_groups.append({'header': 'TOTALES INTERNACIONALES', 'fields': international_total_fields})

        if international_fields:
            international_fields.insert(0,
                {"name": "Número de Declaración Única de Aduana", "field": "declaration_unique_of_customs"}
            )
            international_fields.insert(1,
                {"name": "Número de expediente de Importación", "field": "import_file_number_purchase_international"}
            )
            international_fields.insert(2,
                {"name": "Valor total de las importaciones definitivas", "field": "amount_import_international", "format": "number"}
            )
            purchase_groups.append({'header': 'COMPRAS INTERNACIONALES', 'fields': international_fields})

        no_deductible_fields = []
        if company.config_deductible_tax:
            if company.no_deductible_general_aliquot_purchase:
                no_deductible_fields.extend([
                    {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot_no_deductible", "format": "number"},
                    {"name": "Alicuota (16%)", "field": "general_aliquot_no_deductible", "format": "percent"},
                    {"name": "Crédito Fisc. (16%)", "field": "amount_general_aliquot_no_deductible", "format": "number"}
                ])

            if company.no_deductible_reduced_aliquot_purchase:
                no_deductible_fields.extend([
                    {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot_no_deductible", "format": "number"},
                    {"name": "Alicuota (8%)", "field": "reduced_aliquot_no_deductible", "format": "percent"},
                    {"name": "Crédito Fisc. (8%)", "field": "amount_reduced_aliquot_no_deductible", "format": "number"}
                ])

            if company.no_deductible_extend_aliquot_purchase:
                no_deductible_fields.extend([
                    {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot_no_deductible", "format": "number"},
                    {"name": "Alicuota (31%)", "field": "extend_aliquot_no_deductible", "format": "percent"},
                    {"name": "Crédito Fisc. (31%)", "field": "amount_extend_aliquot_no_deductible", "format": "number"}
                ])

        if no_deductible_fields:
            purchase_groups.append({'header': 'IMPUESTOS NO DEDUCIBLES', 'fields': no_deductible_fields})

        
        return purchase_groups
