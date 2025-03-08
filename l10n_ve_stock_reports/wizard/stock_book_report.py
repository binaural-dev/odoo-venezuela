from collections import defaultdict
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

    incoming_qty = fields.Float(default=0.0)
    
    def generate_report(self):
        return self.download_stock_book()

    def download_stock_book(self):
        self.ensure_one()
        url = "/web/download_stock_book?company_id=%s" % self.company_id.id
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}
    
    def parse_stock_book_data(self):
        stock_book_lines = []
        stock_moves = self.search_stock_moves()

        if not stock_moves:
            _logger.info(f"NO SE IDENTIFICARON STOCK MOVES MEDIANTE EL DOMAIN")

            return
        
        product_movements = defaultdict(lambda: {"incoming": 0.0, "outgoing": 0.0, "stock_move_id":0,"withdraw":0.0})

        for stock_move in stock_moves:
                _logger.info(f"HOLA SOY UNO DE LOS STOCK MOVES DEL DOMAIN:{stock_move.read(['reference','product_id','picking_code','state','is_inventory'])}")
                product_id = stock_move.product_id.id
                quantity_done = stock_move.quantity_done
                stock_move_id = stock_move.id

                if stock_move.picking_code == "incoming" and stock_move.state == "done":
                    # Sumar la cantidad al producto correspondiente en el diccionario
                    product_movements[product_id]["stock_move_id"] = stock_move_id

                    product_movements[product_id]["incoming"] += quantity_done
                
                if stock_move.picking_code == "outgoing" and stock_move.state == "done":
                    # Sumar la cantidad al producto correspondiente en el diccionario
                    product_movements[product_id]["stock_move_id"] = stock_move_id

                    product_movements[product_id]["outgoing"] += quantity_done
                
                if stock_move.is_inventory or stock_move.scrap_ids:
                    _logger.info(f"Este stock.move fue causado por un ajuste de inventario.")
                    product_movements[product_id]["stock_move_id"] = stock_move_id

                    product_movements[product_id]["withdraw"] += quantity_done

                continue

        for product_id, movements in product_movements.items():
            # _logger.info(f"TOTAL DE ENTRADAS POR PRODUCTO: {product_id}, TOTAL INCOMING :{movements["incoming"]}, TOTAL OUTGOING: {movements["outgoing"]}")
            stock_book_line = self._fields_stock_book_line(product_id,movements)
            stock_book_lines.append(stock_book_line)

        
        return stock_book_lines
    
    def search_stock_moves(self):
        order = "id asc"
        env = self.env
        stock_move_model = env["stock.move"]
        domain = self._get_domain_stock_move()
        stock_moves = stock_move_model.search(domain, order=order)

        if not stock_moves:
            return []

        return stock_moves

    def _get_domain_stock_move(self):
        stock_move_search_domain = []

        stock_move_search_domain += [("company_id", "=", self.company_id.id)]

        stock_move_search_domain += [("create_date", ">=", self.date_from)]
        stock_move_search_domain += [("create_date", "<=", self.date_to)]

        return stock_move_search_domain
    
    def _fields_stock_book_line(self,product_id,movements):
        
        return {
            "_id": movements["stock_move_id"],
            "document_date": self.env["product.product"].browse(product_id).name,
            # "accounting_date": self._format_date(move.date),
            # "vat": move.vat,
            "partner_name": movements["incoming"],
            "document_number": movements["withdraw"],
             "move_type": movements["outgoing"],
            # "transaction_type": self._determinate_transaction_type(move),
            # "number_invoice_affected": move.reversed_entry_id.name or "--",
            # "correlative": move.correlative if move.correlative else False,
            # "reduced_aliquot": 0.08,
            # "general_aliquot": 0.16,
            # "total_sales_iva": taxes.get("amount_taxed", 0),
            # "total_sales_not_iva": taxes.get("tax_base_exempt_aliquot", 0) * multiplier,
            # "amount_reduced_aliquot": taxes.get("amount_reduced_aliquot", 0) * multiplier,
            # "amount_general_aliquot": taxes.get("amount_general_aliquot", 0) * multiplier,
            # "tax_base_reduced_aliquot": taxes.get("tax_base_reduced_aliquot", 0) * multiplier,
            # "tax_base_general_aliquot": taxes.get("tax_base_general_aliquot", 0) * multiplier,
        }
    
    # def _determinate_stock_moves_qty(self, move):
    #     is_done = move.state == "done"

    #     tax_result = {}

    #     if move.picking_code == "incoming":
            
            
    #     if not (is_done):
    #         _logger.info("EL MOVIMIENTO NO ESTA COMPLETADO")
    #         return {
                
    #         }

    #     return tax_result
    
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
                "name": "#",
                "field": "index",
            },
            {
                "name": "ITEM DE INVENTARIO",
                "field": "index",
            },
            {
                "name": "DESCRIPCIÓN",
                "field": "document_date",
                "size": 18,
            },
            # {
            #     "name": "EXISTENCIA ANTERIOR", 
            #     "field": "vat", 
            #     "size": 10
            # },
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
                "name": "RETIROS",
                "field": "document_number",
                "size": 10,
            },
            # {
            #     "name": "AUTO-CONSUMOS",
            #     "field": "correlative",
            #     "size": 10,
            # },
            # {
            #     "name": "EXISTENCIA", 
            #     "field": "transaction_type",
            #     "size": 10,
            # },
            # {
            #     "name": "VALOR ANTERIOR EN BS",
            #     "field": "number_invoice_affected",
            #     "size": 15,
            # },
            # {
            #     "name": "ENTRADAS",
            #     "field": "total_sales_iva",
            #     "format": "number",
            #     "size": 20,
            # },
            # {
            #     "name": "SALIDAS",
            #     "field": "total_sales_not_iva",
            #     "format": "number",
            #     "size": 15,
            # },
            # {
            #     "name": "RETIROS",
            #     "field": "tax_base_general_aliquot",
            #     "format": "number",
            #     "size": 15,
            # },
            # {
            #     "name": "AUTO-CONSUMOS",
            #     "field": "general_aliquot",
            #     "format": "percent",
            #     "size": 15,
            # },
            # {
            #     "name": "EXISTENCIA",
            #     "field": "amount_general_aliquot",
            #     "format": "number",
            #     "size": 15,
            # },
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
            {"bold": 1, "font_name":"Arial", "font_size":7 ,"border": 1, "align": "center", "valign": "vcenter",}
        )
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00"}),
            "percent": workbook.add_format({"num_format": "0.00%"}),
        }

        worksheet.merge_range(
            "D2:N2",
            f"REGISTRO DETALLADO DE ENTRADAS Y SALIDAS DE INVENTARIO DE MERCANCÍAS (PRODUCTOS TERMINADOS)",
            workbook.add_format({"border":0,"bold":True ,"center_across": True, "font_size": 12, "font_name":"Arial"}),
        )
        worksheet.merge_range(
            "A4:B4",
            (
                f"Razón Social:{self.company_id.name}"
            ),
            workbook.add_format({"border":0,"bold":True, "font_size": 10, "font_name":"Arial"}),
        )
        worksheet.merge_range(
            "A5:B5",
            (
                f"RIF:{self.company_id.vat}"
            ),
            workbook.add_format({"border":0,"bold":True,"font_size": 10, "font_name":"Arial"}),
        )

        worksheet.merge_range("K4:L4", "Fecha Inicio", workbook.add_format({"border":0,"bold":True ,"center_across":True , "font_size": 10, "font_name":"Arial"}),)

        worksheet.merge_range("K5:L5", f"{self.date_from}", workbook.add_format({"border":0,"center_across":True , "font_size": 10, "font_name":"Arial"}),)

        worksheet.write("M4", "Fecha Fin", workbook.add_format({"border":0,"bold":True ,"center_across":True , "font_size": 10, "font_name":"Arial"}),)

        worksheet.write("M5", f"{self.date_to}", workbook.add_format({"border":0,"center_across":True , "font_size": 10, "font_name":"Arial"}),)


        worksheet.merge_range(
            "D7:I7",
            f"UNIDADES DEL MES",
            workbook.add_format({"border":1, "center_across": True, "font_size": 8, "font_name":"Arial"}),
        )

        worksheet.merge_range(
            "J7:O7",
            f"BOLÍVAR DEL MES",
            workbook.add_format({"border":1, "center_across": True, "font_size": 8, "font_name":"Arial"}),
        )
        

        name_columns = self.stock_book_fields()
        total_idx = 0

        for index, field in enumerate(name_columns):
            worksheet.set_column(index, index, len(field.get("name")) + 2)
            
            worksheet.write(7, index, field.get("name"), merge_format)

            for index_line, line in enumerate(stock_book_lines):
                total_idx = (8 + index_line) + 1

                if field["field"] == "index":
                    worksheet.write(INIT_LINES + index_line, index, index_line + 1)
                else:
                    cell_format = cell_formats.get(field.get("format"), workbook.add_format())
                    worksheet.write(
                        INIT_LINES + index_line, index, line.get(field["field"]), cell_format
                    )

            # Sumatoria Final
            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}9:{col}{total_idx})", workbook.add_format(
                        {"bold": 1, "font_size":7 ,"border": 1, "valign": "vcenter", "fg_color": "silver"}
                    )
                )

        workbook.close()
        return file.getvalue()
    
    