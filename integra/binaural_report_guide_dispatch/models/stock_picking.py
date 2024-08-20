import logging
from datetime import datetime

from odoo import api, fields, models

from ..utils.constants import *
from ..utils.qweb_text import *

_logger = logging.getLogger(__name__)


MAX_CHAR_LINE = 64
CHAR_PER_LINE = 44

class StockPicking(models.Model):
    _inherit = "stock.picking"


    invoice_id = fields.Many2one(
        "account.move",
        domain="[('id','in',available_invoice_ids)]"
    )

    available_invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_available_invoice_ids"
    )


    # Computes
    def _compute_available_invoice_ids(self):
        for record in self:
            record.available_invoice_ids = record.sale_id.invoice_ids


    # Api models
    @api.model
    def get_line_text_border_escpos(self, line):
        return f"| {line.ljust(93)[:93]}|"


    # Functions
    def get_lines_escpos_invoice(self):
        lines = []
        for index, line in enumerate(self.invoice_id.invoice_line_ids):
            index = f"{str( 1 + index)[-3:].rjust(3 - len(str(1 + index)))}"
            code = f"{str(line.product_id.default_code or '')[-12:].rjust(12)}"
            qty = f"{str(line.quantity)[-9:].rjust(9)}"
            udm = f"{str(line.product_uom_id.name)[:6].rjust(6)}"
            description = (
                f"  {str(line.product_id.name if line.product_id else line.name)[:45].ljust(45)}"
            )
            unit_price = f"{str('%.2f'% line.foreign_price)[-15:].rjust(10)}"
            total = f"{str('%.2f'% line.foreign_subtotal)[-15:].rjust(20)}"
            lines.append(index + code + qty + udm + description + unit_price + total)

        if len(self.invoice_id.invoice_line_ids) < self.invoice_id.company_id.max_product_invoice:
            for line in range(self.invoice_id.company_id.max_product_invoice - len(self.invoice_id.invoice_line_ids)):
                lines.append("")

        return lines

    def get_tax_totals_escpos_stock_picking(self,currency):
        # Lines to return
        lines = []

        # Base imponible
        base_name = 'BASE IMPONIBLE'
        base_amount_foreign = ''
        base_amount = ''
       
        # EXENTO 
        tax_name_exento = 'EXENTO DE IVA'
        tax_amount_foreign_exento = ''
        tax_amount_exento = ''

        # IVA 
        tax_name_iva = 'IVA 16%'
        tax_amount_foreign_iva = ''
        tax_amount_iva = ''

        # Total a pagar
        total_name = 'TOTAL A PAGAR'
        total_amount_foreign = ''
        total_amount = ''
        
        if currency == 1:
            # Add line - BASE IMPONIBLE
            lines.append(base_name.ljust(20, " ") + base_amount_foreign)
            # Add line - EXENTO
            lines.append(tax_name_exento.ljust(20, " ") + tax_amount_foreign_exento)
            # Add line - IVA
            lines.append(tax_name_iva.ljust(20, " ") + tax_amount_foreign_iva)
            # Add line - TOTAL MONTO
            lines.append(total_name.ljust(20, " ") + total_amount_foreign)

        elif currency == 2:
            # Add line - BASE IMPONIBLE
            lines.append(base_name.rjust(20, " ") + base_amount_foreign.rjust(20, " ") + base_amount.rjust(14, " "))
            # Add line - EXENTO
            lines.append(tax_name_exento.rjust(20, " ") + tax_amount_foreign_exento.rjust(20, " ") + tax_amount_exento.rjust(14, " "))
            # Add line - IVA
            lines.append(tax_name_iva.rjust(20, " ") + tax_amount_foreign_iva.rjust(20, " ") + tax_amount_iva.rjust(14, " "))
            # Add line - TOTAL MONTO
            lines.append(total_name.rjust(20, " ") + total_amount_foreign.rjust(20, " ") + total_amount.rjust(14, " "))

        return lines

    def _get_payment_info(self):
        invoice_payments_widget = self.invoice_payments_widget
        

        if not invoice_payments_widget:
            return []

        return invoice_payments_widget["content"]

    def get_number_document_guide_dispatch(self):
        preff = self.picking_type_id.sequence_id.prefix
        suff = self.picking_type_id.sequence_id.suffix
        name = self.name 

        if preff:
            name = name.replace(preff, '')
        if suff:
            name = name.replace(suff, '')

        return name

    def get_lines_escpos_stock_picking(self):
        lines = []
        for index, line in enumerate(self.move_line_ids):
            index = f"{str( 1 + index)[-10:].center(10 - len(str(1 + index)))}"
            code = f"{str(line.product_id.default_code or '')[:20].center(21)}"
            qty = f"{str(line.qty_done)[-14:].center(16)}"
            udm = f"{str(line.product_uom_id.name)[:23].center(14)}"
            description = (
                f"  {str(line.product_id.name)[:33].center(36)}"
            )
            lines.append(index + code + qty + udm + description)

        if len(self.move_line_ids) < self.company_id.max_product_invoice:
            for line in range(self.company_id.max_product_invoice - len(self.move_line_ids)):
                lines.append("")

        return lines
    
    def code_monetary_formatted(self, string):
        return string.encode('latin-1').replace(b"\xa0", b" ").replace(b"xc2", b" ").decode('latin-1')