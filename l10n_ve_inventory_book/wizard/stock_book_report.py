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
    _description = "Generate XML Stock Book Report"

    def _default_date_to(self):
        current_day = fields.Date.today()
        return current_day

    def _default_date_from(self):
        today = fields.Date.today()
        return today.replace(day=1)

    def _default_company_id(self):
        company_id = self.env.company.id
        return company_id

    date_from = fields.Date(
        "Inventory at Date",
        help="Start date of the period for the inventory report.",
        default=_default_date_from,
    )

    date_to = fields.Date(
        "Inventory at Date to",
        help="End date of the period for the inventory report.",
        default=_default_date_to,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self._default_currency_id(),
        domain="[('active', '=', True)]"
    )

    product_categ_ids = fields.Many2many(
        'product.category',
        string='Product Categories',
        help="Select one or more product categories to filter the report. If you don't select any category, all products will be included.",
    )

    company_id = fields.Many2one("res.company", default=_default_company_id)

    currency_system = fields.Boolean(string="Report in currency system", default=False)

    include_products_with_no_movements_in_the_month = fields.Boolean(default=False, string="Include products with no movements in the month", help="Include products with no movements in the month in the inventory book")

    incoming_qty = fields.Float(default=0.0)

    def _default_currency_id(self):
        vef_currency = self.env['res.currency'].search([('name', '=', 'VEF'), ('active', '=', True)], limit=1)
        return vef_currency.id if vef_currency else self.env.company.currency_id.id

    def generate_report(self):
        return self.download_stock_book()

    def download_stock_book(self):
        self.ensure_one()
        url = "/web/download_stock_book?company_id=%s" % self.company_id.id
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def parse_stock_book_data(self):
        stock_book_lines = []
        valuation_layers = self.search_valuation_layers()

        if not valuation_layers and not self.include_products_with_no_movements_in_the_month:
            return stock_book_lines

        use_foreign_value = self._should_use_foreign_value()

        product_movements = defaultdict(
            lambda: {
                "incoming": 0.0,
                "outgoing": 0.0,
                "stock_move_id": 0,
                "withdraw": 0.0,
                "incoming_total": 0.0,
                "outgoing_total": 0.0,
                "withdraw_total": 0.0,
                "old_stock": 0.0,
                "self_consumption": 0.0,
                "total_stock_qty_product": 0.0,
                "balance_now": 0.0,
                "self_consumption_total": 0.0,
                "total_stock_qty_product_bs": 0.0,
                "old_stock_total": 0.0,
            }
        )
        stock_move_line_report = self.env['stock.move.line.report']
        field_value = 'monetary_balance_bs' if self._should_use_foreign_value() else 'monetary_balance_usd'
        for stock_move in valuation_layers:

            product_id = stock_move.product_id.id
            quantity_done = stock_move.quantity
            stock_move_id = stock_move.stock_move_id.id

            if use_foreign_value and hasattr(stock_move, 'foreign_value'):
                monetary_value = stock_move.foreign_value
            else:
                monetary_value = stock_move.value

            if product_id not in product_movements:
                data = stock_move_line_report.read_group(['&', ['company_id', '=', self.company_id.id], ['product_id', '=', stock_move.product_id.id]], ['display_reversed_lines', 'date', 'company_id', 'product_id', 'reference', 'warehouse_id', 'origin', 'move_type', 'qty_in', 'qty_out', 'balance', 'is_reverse_line',field_value], ['date:month'],0,80,False,True)
                old_data = self._find_matching_month(data,self.date_from)
                
                product_movements[product_id]["stock_move_id"] = stock_move_id
                product_movements[product_id]["old_stock"] = old_data.get('balance',0.0) if old_data else 0
                product_movements[product_id]["old_stock_total"] = (
                    old_data.get(field_value,0.0) if old_data else 0
                )

            if stock_move.stock_move_id.unbuild_id:
                unbuild = self.env["mrp.unbuild"].browse(
                    stock_move.stock_move_id.unbuild_id.id
                )
                if unbuild:
                    if unbuild.product_id != stock_move.product_id:
                        stock_move.stock_move_id.picking_code = 'incoming'
                    else:
                        stock_move.stock_move_id.picking_code = 'outgoing'

            if stock_move.stock_move_id.production_id or stock_move.stock_move_id.raw_material_production_id:
                
                production = stock_move.stock_move_id.production_id if stock_move.stock_move_id.production_id else stock_move.stock_move_id.raw_material_production_id
                
                if production:
                    if production.product_id == stock_move.product_id and not stock_move.stock_move_id.scrap_id:
                        stock_move.stock_move_id.picking_code = 'incoming'
                    else:
                        stock_move.stock_move_id.picking_code = 'outgoing'
            # incoming
            if (
                (
                    stock_move.stock_move_id.picking_code == "incoming"
                    and stock_move.stock_move_id.state == "done"
                )
                or (
                    stock_move.stock_move_id.is_inventory
                    and stock_move.quantity > 0
                    and stock_move.stock_move_id.state == "done"
                )  
            ):
                product_movements[product_id]["stock_move_id"] = stock_move_id
                product_movements[product_id]["incoming"] += quantity_done
                product_movements[product_id]["incoming_total"] += monetary_value

            # outgoing
            if ((
                    stock_move.stock_move_id.picking_code == "outgoing"
                    and stock_move.stock_move_id.origin_returned_move_id
                    and stock_move.stock_move_id.state == "done" 
                    and not stock_move.stock_move_id.picking_id.transfer_reason_id.code == "self_consumption" 
                    and not stock_move.stock_move_id.scrap_id
                    and not stock_move.stock_move_id.picking_id.transfer_reason_id.code == "donation"
                )
                or (
                    stock_move.stock_move_id.is_inventory
                    and stock_move.quantity < 0
                    and stock_move.stock_move_id.state == "done" 
                )
                or (
                    stock_move.stock_move_id.picking_code == "outgoing"
                    and not (stock_move.stock_move_id.origin_returned_move_id)
                    and stock_move.stock_move_id.state == "done" 
                    and not stock_move.stock_move_id.picking_id.transfer_reason_id.code == "self_consumption" 
                    and not stock_move.stock_move_id.scrap_id
                    and not stock_move.stock_move_id.picking_id.transfer_reason_id.code == "donation"
                )
            ):
                product_movements[product_id]["stock_move_id"] = stock_move_id
                product_movements[product_id]["outgoing"] += quantity_done
                product_movements[product_id]["outgoing_total"] += monetary_value

            # withdraw
            if (
                stock_move.stock_move_id.picking_id
                and stock_move.stock_move_id.picking_id.transfer_reason_id.code
                == "donation"
            ) or stock_move.stock_move_id.scrap_id:
                product_movements[product_id]["stock_move_id"] = stock_move_id
                product_movements[product_id]["withdraw"] += quantity_done
                product_movements[product_id]["withdraw_total"] += monetary_value

            # self_consumption
            if (
                stock_move.stock_move_id.picking_id
                and stock_move.stock_move_id.picking_id.transfer_reason_id.code
                == "self_consumption"
                and not quantity_done >= 0
            ):
                product_movements[product_id]["stock_move_id"] = stock_move_id
                product_movements[product_id]["self_consumption"] += quantity_done
                product_movements[product_id]["self_consumption_total"] += monetary_value
                
            product_movements[product_id]["total_stock_qty_product"] += quantity_done
            product_movements[product_id]["total_stock_qty_product_bs"] += monetary_value
         
        # Add products with no movements in the month
        if self.include_products_with_no_movements_in_the_month:
            product_domain = []
            if self.product_categ_ids:
                product_domain = [('categ_id', 'child_of', self.product_categ_ids.ids)]
            if self.env.company.display_consumables:
                product_domain += [('detailed_type','in', ['product', 'consu'])]  
            else:
                product_domain += [('detailed_type','ilike','product')]
            all_products = self.env['product.product'].search(product_domain)
            for product in all_products:
                if product.id not in product_movements:
                    #Obtain the previous stock for products with no movements in the month
                    data = stock_move_line_report.read_group(
                        ['&', ['company_id', '=', self.company_id.id], ['product_id', '=', product.id]], 
                        ['display_reversed_lines', 'date', 'company_id', 'product_id', 'reference', 'warehouse_id', 'origin', 'move_type', 'qty_in', 'qty_out', 'balance', 'is_reverse_line',field_value], 
                        ['date:month'], 0, 80, False, True
                    )
                    old_data = self._find_matching_month(data, self.date_from)
                                        
                    product_movements[product.id] = {
                        "incoming": 0.0,
                        "outgoing": 0.0,
                        "stock_move_id": 0,
                        "withdraw": 0.0,
                        "incoming_total": 0.0,
                        "outgoing_total": 0.0,
                        "withdraw_total": 0.0,
                        "old_stock": old_data.get('balance', 0.0) if old_data else 0,
                        "self_consumption": 0.0,
                        "total_stock_qty_product": 0.0,
                        "balance_now": old_data.get('balance', 0.0) if old_data else 0,
                        "self_consumption_total": 0.0,
                        "total_stock_qty_product_bs": 0.0,
                        "old_stock_total": old_data.get(field_value, 0.0) if old_data else 0,
                    }

        for product_id, movements in product_movements.items():
            stock_book_line = self._fields_stock_book_line(product_id, movements)
            stock_book_lines.append(stock_book_line)

        return stock_book_lines
    
    def _get_month_title(self):
        self.ensure_one()
        if self.currency_id == self.env.ref("base.VEF"):
            return "BOLÍVARES DEL MES"
        if self.currency_id == self.env.ref("base.USD"):
            return "DÓLARES DEL MES"

    def _should_use_foreign_value(self):
        """
        Determine whether to use foreign_value field based on currency configuration
        :return: Boolean - True if foreign_value should be used, False otherwise
        """
        vef_currency = self.env.ref('base.VEF', raise_if_not_found=False)
        if not vef_currency:
            # VEF currency not found in system, use default value
            return False
            
        system_currency = self.env.company.currency_id
        report_currency = self.currency_id
        
        return (system_currency == vef_currency and report_currency != vef_currency) or \
               (system_currency != vef_currency and report_currency == vef_currency)
    
    def _find_matching_month(self,data, date_from):
        if not date_from:
            return None
        if not data:
            return None
        rest_month = 1
        from_date = fields.Datetime.to_datetime(date_from).date()

        while rest_month <= 12:
            previous_month_date = from_date - relativedelta(months=rest_month)

            for item in data:
                range_from = fields.Datetime.to_datetime(item['__range']['date:month']['from']).date()
                if range_from.month == previous_month_date.month and range_from.year == previous_month_date.year:
                    return item
            rest_month += 1
        
        return None  # If no match is found


    def _get_old_stock_values(self, product_id):
        """
        Get historical stock values for a product
        """
        domain = [
            ("product_id", "=", product_id),
            ("create_date", "<", self.date_from),
            ("create_date", ">=", self.date_from - relativedelta(months=1)),
            ("stock_move_id.state", "=", "done"),
        ]
        
        if self.product_categ_ids:
            product = self.env["product.product"].browse(product_id)
            if not (product.categ_id.id in self.product_categ_ids.ids or 
                    product.categ_id.parent_id.id in self.product_categ_ids.ids):
                return {
                    'total_stock_qty': 0.0,
                    'old_stock_total': 0.0,
                }

        use_foreign_value = self._should_use_foreign_value()
        old_stock_moves = self.env["stock.valuation.layer"].search(domain)
        
        total_qty = 0.0
        total_value = 0.0
        
        for move in old_stock_moves:
            total_qty += move.quantity
            if use_foreign_value and hasattr(move, 'foreign_value'):
                total_value += move.foreign_value
            else:
                total_value += move.value
        
        return {
            'total_stock_qty': total_qty,
            'old_stock_total': total_value,
        }

    def search_valuation_layers(self):
        order = "id asc"
        env = self.env
        valuation_layer_model = env["stock.valuation.layer"]
        domain = self._get_domain_stock_move()
        
        if self.product_categ_ids:
            products = env["product.product"].search([
                ('categ_id', 'child_of', self.product_categ_ids.ids)
            ])
            domain += [('product_id', 'in', products.ids)]

        if env.company.display_consumables:
            domain += [('product_id.type','in', ['product', 'consu'])]  
        else:
            domain += [('product_id.type','ilike','product')]
        
        valuation_layers = valuation_layer_model.search(domain, order=order)

        if not valuation_layers:
            return []

        return valuation_layers

    def _get_domain_stock_move(self):
        stock_move_search_domain = []

        stock_move_search_domain += [("company_id", "=", self.company_id.id)]

        stock_move_search_domain += [("create_date", ">=", self.date_from)]
        stock_move_search_domain += [("create_date", "<=", self.date_to)]

        stock_move_search_domain += [("stock_move_id.state", "=", "done")]

        return stock_move_search_domain

    def _fields_stock_book_line(self, product_id, movements):

        return {
            "_id": movements["stock_move_id"],
            "description": self.env["product.product"].browse(product_id).name,
            "accounting_date": "",
            "old_stock": movements["old_stock"],
            "incoming_stock": movements["incoming"],
            "withdraw": (
                movements["withdraw"]
                if movements["withdraw"] > 0
                else movements["withdraw"] * (-1)
            ),
            "outgoing_stock": (
                movements["outgoing"]
                if movements["outgoing"] > 0
                else movements["outgoing"] * (-1)
            ),
            "stock": movements["old_stock"] + movements["total_stock_qty_product"],
            "old_stock_bs": movements["old_stock_total"],
            "self_con": (
                movements["self_consumption"] if movements["self_consumption"] >= 0 else movements["self_consumption"] *-1
            ),
            "self_consumption_total": (
                movements["self_consumption_total"]
                if movements["self_consumption_total"] > 0
                else movements["self_consumption_total"] * (-1)
            ),
            "incoming_total": movements["incoming_total"],
            "outgoing_total": (
                movements["outgoing_total"]
                if movements["outgoing_total"] > 0
                else movements["outgoing_total"] * (-1)
            ),
            "total_stock_qty_product_bs": movements["total_stock_qty_product_bs"],
            "withdraw_total": (
                movements["withdraw_total"]
                if movements["withdraw_total"] > 0
                else movements["withdraw_total"] * (-1)
            ),
        }

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
                "field": "description",
                "size": 18,
            },
            {
                "name": "EXISTENCIA ANTERIOR",
                "field": "old_stock",
                "size": 10,
                "format": "number",
            },
            {
                "name": "ENTRADAS",
                "field": "incoming_stock",
                "size": 10,
                "format": "number",
            },
            {
                "name": "SALIDAS",
                "field": "outgoing_stock",
                "size": 10,
                "format": "number",
            },
            {
                "name": "RETIROS",
                "field": "withdraw",
                "size": 10,
                "format": "number",
            },
            {
                "name": "AUTO-CONSUMOS",
                "field": "self_con",
                "size": 10,
                "format": "number",
            },
            {
                "name": "EXISTENCIA",
                "field": "stock",
                "size": 10,
                "format": "number",
            },
            {
                "name": "VALOR ANTERIOR EN BS",
                "field": "old_stock_bs",
                "size": 15,
                "format": "number",
            },
            {
                "name": "ENTRADAS",
                "field": "incoming_total",
                "format": "number",
                "size": 20,
                "format": "number",
            },
            {
                "name": "SALIDAS",
                "field": "outgoing_total",
                "format": "number",
                "size": 15,
                "format": "number",
            },
            {
                "name": "RETIROS",
                "field": "withdraw_total",
                "format": "number",
                "size": 15,
            },
            {
                "name": "AUTO-CONSUMOS",
                "field": "self_consumption_total",
                "format": "number",
                "size": 15,
            },
            {
                "name": "EXISTENCIA",
                "field": "total_stock_qty_product_bs",
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

        workbook = xlsxwriter.Workbook(
            file,
            {
                "in_memory": True,
                "nan_inf_to_errors": True,
                "calc_mode": "auto",
            },
        )
        worksheet = workbook.add_worksheet()

        merge_format = workbook.add_format(
            {
                "bold": 1,
                "font_name": "Arial",
                "font_size": 7,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        cell_formats = {
            "number": workbook.add_format({"num_format": "#,##0.00"}),
            "percent": workbook.add_format({"num_format": "0.00%"}),
        }

        worksheet.merge_range(
            "D2:N2",
            f"REGISTRO DETALLADO DE ENTRADAS Y SALIDAS DE INVENTARIO DE MERCANCÍAS",
            workbook.add_format(
                {
                    "border": 0,
                    "bold": True,
                    "center_across": True,
                    "font_size": 12,
                    "font_name": "Arial",
                }
            ),
        )
        worksheet.merge_range(
            "A4:D4",
            (f"Razón Social: {self.company_id.name}"),
            workbook.add_format(
                {"border": 0, "bold": True, "font_size": 10, "font_name": "Arial"}
            ),
        )
        worksheet.merge_range(
            "A5:B5",
            (f"RIF:{self.company_id.vat}"),
            workbook.add_format(
                {"border": 0, "bold": True, "font_size": 10, "font_name": "Arial"}
            ),
        )

        worksheet.merge_range(
            "K4:L4",
            "Fecha Inicio",
            workbook.add_format(
                {
                    "border": 0,
                    "bold": True,
                    "center_across": True,
                    "font_size": 10,
                    "font_name": "Arial",
                }
            ),
        )

        worksheet.merge_range(
            "K5:L5",
            f"{self.date_from}",
            workbook.add_format(
                {
                    "border": 0,
                    "center_across": True,
                    "font_size": 10,
                    "font_name": "Arial",
                }
            ),
        )

        worksheet.merge_range(
            "M4:N4",
            "Fecha Fin",
            workbook.add_format(
                {
                    "border": 0,
                    "bold": True,
                    "center_across": True,
                    "font_size": 10,
                    "font_name": "Arial",
                }
            ),
        )

        worksheet.merge_range(
            "M5:N5",
            f"{self.date_to}",
            workbook.add_format(
                {
                    "border": 0,
                    "center_across": True,
                    "font_size": 10,
                    "font_name": "Arial",
                }
            ),
        )

        worksheet.merge_range(
            "D7:I7",
            f"UNIDADES DEL MES",
            workbook.add_format(
                {
                    "border": 1,
                    "center_across": True,
                    "font_size": 8,
                    "font_name": "Arial",
                }
            ),
        )

        worksheet.merge_range(
            "J7:O7",
            self._get_month_title(),
            workbook.add_format(
                {
                    "border": 1,
                    "center_across": True,
                    "font_size": 8,
                    "font_name": "Arial",
                }
            ),
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
                    cell_format = cell_formats.get(
                        field.get("format"), workbook.add_format()
                    )
                    worksheet.write(
                        INIT_LINES + index_line,
                        index,
                        line.get(field["field"]),
                        cell_format,
                    )

            # Final sum
            if field.get("format") == "number":
                col = utility.xl_col_to_name(index)
                sum_format = workbook.add_format(
                    {
                        "bold": 1,
                        "font_size": 7,
                        "border": 1,
                        "valign": "vcenter",
                        "fg_color": "silver",
                        "num_format": "#,##0.00",
                    }
                )
                worksheet.write_formula(
                    total_idx, index, f"=SUM({col}9:{col}{total_idx})", sum_format
                )

        workbook.close()
        return file.getvalue()
