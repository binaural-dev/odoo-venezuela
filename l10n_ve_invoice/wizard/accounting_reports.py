import logging
from datetime import datetime
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta
from odoo import fields, models, _
from odoo.exceptions import UserError
from xlsxwriter import utility

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
        if not move.invoice_date:
            raise UserError(_("Check the move %s does not have an invoice date and its id is %s", move.name, move.id))
        multiplier = -1 if move.move_type == "out_refund" else 1

        return {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date),
            "accounting_date": self._format_date(move.date),
            "vat": move.vat or '--',
            "partner_name": move.invoice_partner_display_name,
            "document_number": move.name,
            "move_type": self._determinate_type_for_move(move),
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
            "move_type": self._determinate_type_for_move(move),
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": move.debit_origin_id.name if move.journal_id.is_debit else move.reversed_entry_id.name or "--",
            "correlative": move.correlative if not move.declaration_unique_of_customs else "-",
            "reduced_aliquot": 0.08,
            "extend_aliquot": 0.31,
            "general_aliquot": 0.16,
            "total_purchases": taxes.get("amount_taxed", 0),
            "total_purchases_iva": taxes.get("amount_taxed", 0) - (taxes.get("tax_base_exempt_aliquot", 0) * multiplier),
            "total_purchases_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            "amount_extend_aliquot": taxes.get("amount_extend_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
            "tax_base_extend_aliquot": taxes.get("tax_base_extend_aliquot", 0) * multiplier,
        }

        fields_purchase_book_line.update(
            {   "total_purchases_national": taxes.get("national_amount_taxed", 0),
                "total_purchases_iva_national": taxes.get("national_amount_taxed", 0) - (taxes.get("national_tax_base_exempt_aliquot", 0) * multiplier),
                "total_purchases_not_iva_national": taxes.get("national_tax_base_exempt_aliquot", 0) * multiplier,
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
                "name": "Tipo",
                "field": "move_type",
                "size": 16,
            },
            {
                "name": "N° de documento",
                "field": "document_number",
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
            
        if hasattr(self, 'account_analytic_id') and self.account_analytic_id:

            if self.account_analytic_id.name == "Main Subsidiary":
                
                all_subsidiaries = self.env['account.analytic.account'].search([
                    ('is_subsidiary', '=', True),
                    ('company_id', '=', self.company_id.id)
                ])
                if all_subsidiaries:
                    search_domain += [("account_analytic_id", "in", all_subsidiaries.ids)]
            else:
                
                search_domain += [("account_analytic_id", "=", self.account_analytic_id.id)]
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
        env = self.env
        move_model = env["account.move"]
        domain = self._get_domain()
        moves = move_model.search(domain, order="invoice_date asc")

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
                "national_amount_taxed":0.0,
                "national_tax_base_exempt_aliquot": 0.0,
                "international_amount_taxed":0.0,
                "international_tax_base_exempt_aliquot": 0.0,
                "amount_import_international": 0,
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

        national_amount_taxed = (
            tax_totals.get(fields_taxed[1]) * -1
            if is_credit_note and tax_totals.get(fields_taxed[1])
            else tax_totals.get(fields_taxed[1])
        ) if tax_totals and not move.journal_id.is_purchase_international else 0

        international_amount_taxed = (
            tax_totals.get(fields_taxed[1]) * -1
            if is_credit_note and tax_totals.get(fields_taxed[1])
            else tax_totals.get(fields_taxed[1])
        ) if tax_totals and move.journal_id.is_purchase_international else 0

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
                "national_amount_taxed":national_amount_taxed if not move.journal_id.is_purchase_international else 0,
                "international_amount_taxed":international_amount_taxed if move.journal_id.is_purchase_international else 0,
                "national_tax_base_exempt_aliquot": 0.0,
                "international_tax_base_exempt_aliquot": 0.0,
                "amount_import_international": 0,
                "tax_base_reduced_aliquot_international": 0,
                "amount_reduced_aliquot_international": 0,
                "tax_base_general_aliquot_international": 0,
                "amount_general_aliquot_international": 0,
                "tax_base_extend_aliquot_international": 0,
                "amount_extend_aliquot_international": 0,
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
                if move.journal_id.is_purchase_international:
                    exent_aliquot = self.company_id.exent_aliquot_purchase_international.tax_group_id.id
                    if not self.company_id.not_show_general_aliquot_purchase_international:
                        general_aliquot = self.company_id.general_aliquot_purchase_international.tax_group_id.id

                    if not self.company_id.not_show_reduced_aliquot_purchase_international:
                        reduced_aliquot = self.company_id.reduced_aliquot_purchase_international.tax_group_id.id

                    if not self.company_id.not_show_extend_aliquot_purchase_international:
                        extend_aliquot = self.company_id.extend_aliquot_purchase_international.tax_group_id.id
                   
                    
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
                            "national_tax_base_exempt_aliquot": tax.get("tax_group_base_amount") if not move.journal_id.is_purchase_international else 0,
                            "international_tax_base_exempt_aliquot": tax.get("tax_group_base_amount") if move.journal_id.is_purchase_international else 0
                        }
                    )

                is_reduced_aliquot = tax_group_id == reduced_aliquot
                if is_reduced_aliquot:
                    base_key = "tax_base_reduced_aliquot_international" if move.journal_id.is_purchase_international else "tax_base_reduced_aliquot"
                    amount_key = "amount_reduced_aliquot_international" if move.journal_id.is_purchase_international else "amount_reduced_aliquot"
                    tax_result.update(
                        {
                            base_key: tax.get("tax_group_base_amount"),
                            amount_key: tax.get("tax_group_amount"),
                        }
                    )
                    continue

                is_general_aliquot = tax_group_id == general_aliquot
                if is_general_aliquot:
                    base_key = "tax_base_general_aliquot_international" if move.journal_id.is_purchase_international else "tax_base_general_aliquot"
                    amount_key = "amount_general_aliquot_international" if move.journal_id.is_purchase_international else "amount_general_aliquot"
                    tax_result.update(
                        {
                            base_key: tax.get("tax_group_base_amount"),
                            amount_key: tax.get("tax_group_amount"),
                        }
                    )
                    continue

                is_extend_aliquot = tax_group_id == extend_aliquot
                if is_extend_aliquot:
                    base_key = "tax_base_extend_aliquot_international" if move.journal_id.is_purchase_international else "tax_base_extend_aliquot"
                    amount_key = "amount_extend_aliquot_international" if move.journal_id.is_purchase_international else "amount_extend_aliquot"
                    tax_result.update(
                        {
                            base_key: tax.get("tax_group_base_amount"),
                            amount_key: tax.get("tax_group_amount"),
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

        amount_import_international = 0.0
        if move.journal_id.is_purchase_international:
            amount_import_international += tax_result.get("international_tax_base_exempt_aliquot", 0.0)
            if not self.company_id.not_show_general_aliquot_purchase_international:
                amount_import_international += tax_result.get("tax_base_general_aliquot_international", 0.0) + tax_result.get("amount_general_aliquot_international", 0.0)
            
            if not self.company_id.not_show_reduced_aliquot_purchase_international:
                amount_import_international += tax_result.get("tax_base_reduced_aliquot_international", 0.0) + tax_result.get("amount_reduced_aliquot_international", 0.0)
                
            if not self.company_id.not_show_extend_aliquot_purchase_international:
                amount_import_international += tax_result.get("tax_base_extend_aliquot_international", 0.0) + tax_result.get("amount_extend_aliquot_international", 0.0)

        tax_result['amount_import_international'] = amount_import_international

        return tax_result

    def generate_sales_book(self, company_id):

        self.company_id = company_id
        sale_book_lines = self.parse_sale_book_data()
        file = BytesIO()

        password_protection = "secure"
        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
        worksheet = workbook.add_worksheet()

        worksheet.set_landscape()
        worksheet.set_paper(1)
        worksheet.set_margins(left=0.3, right=0.3, top=0.4, bottom=0.4)
        worksheet.fit_to_pages(1, 0)

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
        
        ventas_internas_start_col = 0
        ventas_internas_end_col = 0

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
            
            if group['header'] != 'DETALLE DEL DOCUMENTO' and ventas_internas_start_col == 0:
                ventas_internas_start_col = start_col
            
            if group['header'] == 'ALÍCUOTA ADICIONAL (31%)':
                ventas_internas_end_col = end_col
            
            for field in group_fields:
                col_index = current_col_index

                worksheet.write(6, col_index, field.get("name"), header_format)

                col_width = field.get("size", 14)
                if col_width is None:
                    col_width = 20
                worksheet.set_column(col_index, col_index, col_width)
                flat_fields.append(field)

                current_col_index += 1
            
            color_index += 1 
        
        last_col_index = current_col_index - 1
        
        if ventas_internas_end_col == 0:
            ventas_internas_end_col = last_col_index
        
        if ventas_internas_start_col > 0 and ventas_internas_end_col > 0:
            ventas_internas_start_name = utility.xl_col_to_name(ventas_internas_start_col)
            ventas_internas_end_name = utility.xl_col_to_name(ventas_internas_end_col)
            ventas_internas_range = f"{ventas_internas_start_name}5:{ventas_internas_end_name}5"
            
            ventas_internas_format = workbook.add_format({
                "bold": True, 
                "border": 1, 
                "align": "center", 
                "valign": "vcenter", 
                "bg_color": "#4472C4",
                "font_color": "#FFFFFF",
                "locked": True
            })
            
            worksheet.merge_range(
                ventas_internas_range,
                "Ventas Internas",
                ventas_internas_format
            ) 
                
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
        
            # if field.get("field") == "bi_igtf":
            #     worksheet.write(
            #     total_idx, index, f'=SUMIFS({col}8:{col}{total_idx}, E8:E{total_idx}, "<>NC")*3/100', cell_formats.get("number")
            # )
            if field.get("field") == "igtf":
                worksheet.write(
                total_idx, index, f'=SUM({col}8:{col}{total_idx})', cell_formats.get("number")
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

        worksheet.set_landscape()
        worksheet.set_paper(1)
        worksheet.set_margins(left=0.3, right=0.3, top=0.4, bottom=0.4)
        worksheet.fit_to_pages(1, 0)

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

                col_width = field.get("size", 14)
                if col_width is None:
                    col_width = 20
                worksheet.set_column(col_index, col_index, col_width)
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
                
            # if field.get("field") == "bi_igtf":
            #     worksheet.write(
            #     total_idx, index, f'=SUMIFS({col}8:{col}{total_idx}, E8:E{total_idx}, "<>NC")*3/100', cell_formats.get("number")
            # )
            if field.get("field") == "igtf":
                worksheet.write(
                total_idx, index, f'=SUM({col}8:{col}{total_idx})', cell_formats.get("number")
            )
        
        self.generate_book_resume(worksheet, total_idx, merge_format, cell_formats, last_col_index)

        worksheet.protect(password=password_protection)

        workbook.close()
        return file.getvalue()
        
    def generate_book_resume(self, worksheet, index_to_start, merge_format, cell_formats,last_col_index=5):
        is_purchase = self.report == "purchase"
        header_idx = index_to_start + 2
        resume_headers = self.resume_book_headers()
        
        # Aumentar el ancho de la columna de descripción (columna B, índice 1)
        # para mejorar la legibilidad de los nombres en el resumen
        worksheet.set_column(1, 1, 50)

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
            {"name": "N° operacion", "field": "index", "size": 6},
            {"name": "Fecha del documento", "field": "document_date", "size": 12},
            {"name": "RIF", "field": "vat", "size": 12},
            {"name": "Nombre/Razón social", "field": "partner_name", "size": 20},
            {"name": "Tipo", "field": "move_type", "size": 6},
            {"name": "N° de documento", "field": "document_number", "size": 14},
            {"name": "N° de control", "field": "correlative", "size": 12},
            {"name": "Tipo de transacción", "field": "transaction_type", "size": 10},
            {"name": "N° Factura afectada", "field": "number_invoice_affected", "size": 14},
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
            {"name": "IVA 16%", "field": "amount_general_aliquot", "format": "number", "size": 16},
        ]
        sale_groups.append({'header': 'ALÍCUOTA GENERAL (16%)', 'fields': general_aliquot_fields})

        reduced_aliquot_fields = []
        if not company.not_show_reduced_aliquot_sale:
            reduced_aliquot_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot", "format": "number"},
                {"name": "IVA 8%", "field": "amount_reduced_aliquot", "format": "number"}
            ])

        if reduced_aliquot_fields:
            sale_groups.append({'header': 'ALÍCUOTA REDUCIDA (8%)', 'fields': reduced_aliquot_fields})

        extend_aliquot_fields = []
        if not company.not_show_extend_aliquot_sale:
            extend_aliquot_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot", "format": "number"},
                {"name": "IVA 31%", "field": "amount_extend_aliquot", "format": "number"}
            ])
            
        if extend_aliquot_fields:
            sale_groups.append({'header': 'ALÍCUOTA ADICIONAL (31%)', 'fields': extend_aliquot_fields})

        return sale_groups
    

    def _get_purchase_book_field_groups(self):
        company = self.company_id
        purchase_groups = []

        basic_fields = [
            {"name": "N° operacion", "field": "index", "size": 6},
            {"name": "Fecha del documento", "field": "document_date", "size": 12},
            {"name": "RIF", "field": "vat", "size": 12},
            {"name": "Nombre/Razón social", "field": "partner_name", "size": 20},
            {"name": "Tipo", "field": "move_type", "size": 6},
            {"name": "N° de documento", "field": "document_number", "size": 14},
            {"name": "N° de control", "field": "correlative", "size": 12},
            {"name": "Tipo de transacción", "field": "transaction_type", "size": 10},
            {"name": "N° Factura afectada", "field": "number_invoice_affected", "size": 14},
        ]
        purchase_groups.append({'header': 'DETALLE DEL DOCUMENTO', 'fields': basic_fields})

        total_fields = [
            {"name": "Total compras", "field": "total_purchases", "format": "number", "size": 16},
            {"name": "Total compras con IVA", "field": "total_purchases_iva", "format": "number", "size": 16},
            {"name": "Total compras exentas", "field": "total_purchases_not_iva", "format": "number", "size": 16},
        ]
        purchase_groups.append({'header': 'TOTALES', 'fields': total_fields})

        national_total_fields = [
        ]

        if not company.not_show_total_purchases_national:
            national_total_fields.append(            
                {"name": "Total compras", "field": "total_purchases_national", "format": "number"},
            )

        if not company.not_show_total_purchases_with_iva:
            national_total_fields.append(            
                {"name": "Total compras con IVA", "field": "total_purchases_iva_national", "format": "number"},
            )

        if not company.not_show_national_exempt_total_purchases:
            national_total_fields.append(            
                {"name": "Total compras exentas", "field": "total_purchases_not_iva_national", "format": "number"},
            )

        if national_total_fields:
            purchase_groups.append({'header': 'TOTALES NACIONALES', 'fields': national_total_fields})

        national_deductible_fields = []

        national_deductible_fields.extend([
            {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot", "format": "number", "size": 16},
            {"name": "IVA 16%", "field": "amount_general_aliquot", "format": "number", "size": 16},
        ])

        if not company.not_show_reduced_aliquot_purchase:
            national_deductible_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot", "format": "number"},
                {"name": "IVA 8%", "field": "amount_reduced_aliquot", "format": "number"}
            ])

        if not company.not_show_extend_aliquot_purchase:
            national_deductible_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot", "format": "number"},
                {"name": "IVA 31%", "field": "amount_extend_aliquot", "format": "number"}
            ])

        if national_deductible_fields:
            purchase_groups.append({'header': 'COMPRAS NACIONALES', 'fields': national_deductible_fields})

        international_fields = []
        if not company.not_show_general_aliquot_purchase_international:
            international_fields.extend([
                {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot_international", "format": "number"},
                {"name": "IVA Int. 16%", "field": "amount_general_aliquot_international", "format": "number"}
            ])

        if not company.not_show_reduced_aliquot_purchase_international:
            international_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot_international", "format": "number"},
                {"name": "IVA Int. 8%", "field": "amount_reduced_aliquot_international", "format": "number"}
            ])

        if not company.not_show_extend_aliquot_purchase_international:
            international_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot_international", "format": "number"},
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
                {"name": "Número de Declaración Única de Aduana", "field": "declaration_unique_of_customs", "size": 16}
            )
            international_fields.insert(1,
                {"name": "Valor total de las importaciones definitivas", "field": "amount_import_international", "format": "number", "size": 14}
            )
            purchase_groups.append({'header': 'COMPRAS INTERNACIONALES', 'fields': international_fields})

        no_deductible_fields = []
        if company.config_deductible_tax:
            if company.no_deductible_general_aliquot_purchase:
                no_deductible_fields.extend([
                    {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot_no_deductible", "format": "number"},
                    {"name": "Crédito Fisc. (16%)", "field": "amount_general_aliquot_no_deductible", "format": "number"}
                ])

            if company.no_deductible_reduced_aliquot_purchase:
                no_deductible_fields.extend([
                    {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot_no_deductible", "format": "number"},
                    {"name": "Crédito Fisc. (8%)", "field": "amount_reduced_aliquot_no_deductible", "format": "number"}
                ])

            if company.no_deductible_extend_aliquot_purchase:
                no_deductible_fields.extend([
                    {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot_no_deductible", "format": "number"},
                    {"name": "Crédito Fisc. (31%)", "field": "amount_extend_aliquot_no_deductible", "format": "number"}
                ])

        if no_deductible_fields:
            purchase_groups.append({'header': 'IMPUESTOS NO DEDUCIBLES', 'fields': no_deductible_fields})

        
        return purchase_groups