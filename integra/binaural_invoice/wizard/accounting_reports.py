from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from datetime import datetime
from io import BytesIO

from odoo.exceptions import ValidationError
from odoo import models, fields, _

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
            sale_book_line = {
                "operation_number": count,
                "document_date": move.date,
                "vat": move.vat,
                "partner_name": move.invoice_partner_display_name,
                "document_number": move.name,
                "move_type": move.move_type,
                "number_invoice_affected": move.reversed_entry_id.name,
                "IVA8%": 0.08,
                "IVA16%": 0.16,
                "IVA32%": 0.32,
                "total_sales_iva": 0.0,
                "total_sales_not_iva": 0.0
            }

            sale_book_lines.append(sale_book_line)



    def sale_book_fields(self):
        return [
            {"name": "N° operacion"},
            {"name": "Fecha del documento", "field": "date"},
            {"name": "Nombre/Razón Social", "field": "invoice_partner_display_name"},
            {"name": "tipo", "field": "move_type"},
            {"name": "RIF", "field": "vat"},
            {"name": "N° de documento", "field": "name"},
            {"name": "N° Factura Afectada", "fields": ["reversed_entry_id", "name"]},
            {"name": "Total ventas con IVA", "fields": []},
            {"name": "Total ventas exentas", "fields": []},
            {"name": "IVA 16%", "value": 0.16},
            {"name": "IVA 8%", "value": 0.08},
            {"name": "IVA 32%", "value": 0.32},
            {"name": ""}
        ]
        return [
                # amount_total if move.move_type in ["out_invoice", "out_debit"] else -move.amount_total
                {"name": "Total ventas con IVA", "field": "total_with_tax", "number": True},
                # revisar logica de not_gravable
                {"name": "Total ventas exentas", "field": "total_without_tax", "number": True},
                
                {"name": "Base imponible", "field": "tax_base_16", "number": True},
                {"name": "Imponible16", "field": "aliquot_16"},
                # impuesto 0.16
                {"name": "IVA 16%", "field": "tax_amount_16", "number": True},
                {"name": "Base imponible", "field": "tax_base_8", "number": True},
                {"name": "Alícuota", "field": "aliquot_8"},
                # impuesto 0.08
                {"name": "IVA 8%", "field": "tax_amount_8", "number": True},
                {"name": "Base imponible", "field": "tax_base_31", "number": True},
                {"name": "Alícuota", "field": "aliquot_31"},
                # impuesto 0.31
                {"name": "IVA 31%", "field": "tax_amount_31", "number": True},
                # esto es retenciones asi que solo deben exitir en el excel
                #{"name": "Fecha Retencion", "field": "date_retention_receipt"},
                #{"name": "N° Retencion", "field": "retention_receipt"},
                #{"name": "IVA retenido", "field": "iva_retention", "number": True}
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

    def search_moves(self):
        env = self.env
        move_model = env['account.move']
        domain = self._get_domain()
        return move_model.search(domain)

    def generate_sales_book(self):
        moves = self.search_moves()
        for move in moves:
            for field in move._fields:
                _logger.warning(f"{field}: {move[field]}")

    def generate_purchases_book(self):
        pass
