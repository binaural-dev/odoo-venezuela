import logging
from datetime import datetime, timedelta
from io import BytesIO

import xlsxwriter
from dateutil.relativedelta import relativedelta
from odoo import fields, models
from xlsxwriter import utility

_logger = logging.getLogger(__name__)
INIT_LINES = 8


class WizardStockBookReport(models.TransientModel):
    _name = "wizard.stock.book.report"
    _description = "Wizard para generar reportes de libro de inventario"

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

    date_from = fields.Date('Inventory at Date',
        help="Choose a date to get the inventory at that date",
        default=_default_date_from)
    
    date_to = fields.Date('Inventory at Date to',
        # help="Choose a date to get the inventory at that date",
        default=_default_date_to)
    
    company_id = fields.Many2one("res.company", default=_default_company_id)

    currency_system = fields.Boolean(string="Report in currency system", default=False)
    
    def generate_report(self):
        
        return self.download_stock_book()

    def download_stock_book(self):
        self.ensure_one()
        url = "/web/download_stock_book?company_id=%s" % self.company_id.id
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}
    
    def parse_stock_book_data(self):
        stock_book_lines = []
        moves = self.search_moves()

        if not moves:
            _logger.info(f"NO SE IDENTIFICARON MOVES MEDIANTE EL DOMAIN")

            return
        
        for move in moves:
            _logger.info(f"HOLA SOY UNO DE LOS ACCOUNT MOVE DEVUELTOS POR EL SEARCH MOVES:{move.name}, Valuation al que pertenezco:{move.stock_valuation_layer_ids}, FECHA:{move.date}, INVOICE DATE: {move.invoice_date}, VAT:{move.vat},Tipo:{move.move_type},REVERSED ENTRY: {move.reversed_entry_id.name}")
            taxes = self._determinate_amount_taxeds(move)
            stock_book_line = self._fields_stock_book_line(move, taxes)
            stock_book_lines.append(stock_book_line)
        return stock_book_lines
    
    def search_moves(self):
        order = "id asc"
        env = self.env
        valuation_model = env["stock.valuation.layer"]
        domain = self._get_domain_valuation_layer()
        valuation_layers = valuation_model.search(domain, order=order)

        if not valuation_layers:
            return []
        
        _logger.info(f"SOY LOS VALUATION LAYERS DE LA BUSQUEDA CON EL DOMAIN:{valuation_layers.read()}")

        account_moves = []

        for valuation_layer in valuation_layers:
            account_moves.append(valuation_layer.account_move_id)

        return account_moves

    def _get_domain_valuation_layer(self):
        valuation_search_domain = []

        valuation_search_domain += [("company_id", "=", self.company_id.id)]

        valuation_search_domain += [("create_date", ">=", self.date_from)]
        valuation_search_domain += [("create_date", "<=", self.date_to)]
        valuation_search_domain += [
            ("account_move_id.state", "in", ("posted", "cancel")),
        ]

        return valuation_search_domain
    
    def _fields_stock_book_line(self, move, taxes):
        multiplier = -1 if move.move_type == "out_refund" else 1
        return {
            "_id": move.id,
            "document_date": self._format_date(move.invoice_date) if move.invoice_date else self._format_date(move.date),
            "accounting_date": self._format_date(move.date),
            "vat": move.vat,
            "partner_name": move.invoice_partner_display_name,
            "document_number": move.name,
            "move_type": self._determinate_type(move.move_type),
            "transaction_type": self._determinate_transaction_type(move),
            "number_invoice_affected": move.reversed_entry_id.name or "--",
            "correlative": move.correlative if move.correlative else False,
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "total_sales_iva": taxes.get("amount_taxed", 0),
            "total_sales_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
        }
    
    def _determinate_amount_taxeds(self, move):
        is_posted = move.state == "posted"
        vef_base = self.company_id.currency_id.id == self.env.ref("base.VEF").id

        if not (is_posted and move.tax_totals):
            _logger.info("EL MOVIMIENTO NO POSEE TAX TOTALS O NO ESTA POSTEADO")
            return {
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

        is_currency_system = (
            "groups_by_subtotal"
            if vef_base or self.currency_system
            else "groups_by_foreign_subtotal"
        )
        tax_base = tax_totals.get(is_currency_system)

        for base in tax_base.items():
            taxes = base[1]

            exent_aliquot = False
            general_aliquot = False
            reduced_aliquot = False
            extend_aliquot = False

            exent_aliquot = self.company_id.exent_aliquot_sale.tax_group_id.id
            reduced_aliquot = self.company_id.reduced_aliquot_sale.tax_group_id.id
            general_aliquot = self.company_id.general_aliquot_sale.tax_group_id.id
            extend_aliquot = self.company_id.extend_aliquot_sale.tax_group_id.id

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

        return tax_result
    
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
            "entry":"SI",
        }

        return types[move_type]
    
    def _determinate_transaction_type(self, move):
        if move.move_type in ["out_invoice", "in_invoice"] and move.state == "posted":
            return "01-REG"

        if move.move_type in ["out_debit", "in_debit"] and move.state == "posted":
            return "02-REG"

        if move.move_type in ["out_refund", "in_refund"] and move.state == "posted":
            return "03-REG"
        
        if move.move_type in ["entry"] and move.state == "posted":
            return "04-REG"

        if move.move_type in [
            "out_refund",
            "out_debit",
            "out_invoice",
            "in_refund",
            "in_debit",
            "in_invoice",
        ] and move.state in ["cancel"]:
            return "03-ANU"
    
    def stock_book_fields(self):
        return [
            {
                "name": "N°",
                "field": "index",
            },
            {
                "name": "CODIGO",
                "field": "index",
            },
            {
                "name": "MERCANCIA\n(ARTICULOS O PRODUCTOS)",
                "field": "document_date",
                "size": 18,
            },
            {
                "name": "EXISTENCIA\nINICIAL", 
                "field": "vat", 
                "size": 10
            },
            {
                "name": "ENTRADAS",
                "field": "partner_name",
                "size": 10,
            },
            {
                "name": "SALIDAS",
                "field": "move_type",
                "size": 10,
            },
            {
                "name": "RETIRO",
                "field": "document_number",
                "size": 10,
            },
            {
                "name": "AUTO\nCONSUMO",
                "field": "correlative",
                "size": 10,
            },
            {
                "name": "EXISTENCIA\nFINAL", 
                "field": "transaction_type",
                "size": 10,
            },
            {
                "name": "COSTO\nUNITARIO",
                "field": "number_invoice_affected",
                "size": 15,
            },
            {
                "name": "EXISTENCIA\nINICIAL",
                "field": "total_sales_iva",
                "format": "number",
                "size": 15,
            },
            {
                "name": "ENTRADAS",
                "field": "total_sales_not_iva",
                "format": "number",
                "size": 15,
            },
            {
                "name": "SALIDAS",
                "field": "tax_base_general_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "RETIRO",
                "field": "general_aliquot",
                "format": "percent",
                "size": 15,
            },
            {
                "name": "AUTO\nCONSUMO",
                "field": "amount_general_aliquot",
                "format": "number",
                "size": 15,
            },
            {
                "name": "EXISTENCIA\nFINAL",
                "field": "tax_base_reduced_aliquot",
                "format": "number",
                "size": 15,
            },
        ]
    
    def generate_stocks_book(self, company_id):
        self.company_id = company_id
        stock_book_lines = self.parse_stock_book_data()
        if not stock_book_lines:
            stock_book_lines = []
        file = BytesIO()

        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
        worksheet = workbook.add_worksheet()

        # cell formats
        cell_bold = workbook.add_format(
            {"bold": True, "text_wrap": True, "bottom": True}
        )
        merge_format = workbook.add_format(
            {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "gray"}
        )
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00"}),
            "percent": workbook.add_format({"num_format": "0.00%"}),
        }

        worksheet.merge_range(
            "C1:H1",
            f"LIBRO DE INVENTARIO DE MERCANCIAS (CONFORME AL ART. 177 REGLAMENTO LEY ISLR)",
            workbook.add_format({"bold": True, "border":2, "center_across": True, "font_size": 12}),
        )
        worksheet.merge_range(
            "D3:J3", 
            f"EMPRESA: {self.company_id.name}", 
            cell_bold
        )
        worksheet.merge_range(
            "D4:F4", 
            f"RIF: {self.company_id.vat}", 
            cell_bold
        )
        worksheet.merge_range(
            "D5:H5",
            (
                f"PERIODO: DESDE {self.date_from}"
                f" HASTA {self.date_to}"
            ),
            cell_bold,
        )
        worksheet.merge_range(
            "D6:I6",
            (
                "UNIDADES DE INVENTARIO"
            ),
            workbook.add_format(
                {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "silver"}
            ),
        )
        worksheet.merge_range(
            "J6:P6",
            (
                "UNIDAD MONETARIA (VALORES EXPRESADOS EN BOLIVARES)"
            ),
            workbook.add_format(
                {"bold": 1, "border": 1, "align": "center", "valign": "vcenter", "fg_color": "silver"}
            ),
        )

        name_columns = self.stock_book_fields()
        total_idx = 0

        for index, field in enumerate(name_columns):
            worksheet.set_column(index, index, len(field.get("name")) + 2)
            worksheet.merge_range(6, index, 7, index, field.get("name"), merge_format)

            for index_line, line in enumerate(stock_book_lines):
                total_idx = (8 + index_line) + 1

                if field["field"] == "index":
                    worksheet.write(INIT_LINES + index_line, index, index_line + 1)
                else:
                    cell_format = cell_formats.get(field.get("format"), workbook.add_format())
                    worksheet.write(
                        INIT_LINES + index_line, index, line.get(field["field"]), cell_format
                    )
            
            #Sumatoria Final
            if field.get("format") == "number":

                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}9:{col}{total_idx})", workbook.add_format(
                        {"bold": 1, "border": 1, "valign": "vcenter", "fg_color": "silver"}
                    )
                )

        workbook.close()
        return file.getvalue()
    
    