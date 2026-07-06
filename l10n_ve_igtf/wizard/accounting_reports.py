from odoo import _, api, models

import logging

_logger = logging.getLogger(__name__)

class WizardAccountingReports(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    def sale_book_fields(self):
        fields = super().sale_book_fields()
        fields.append(
            {
                "name": "IGTF",
                "field": "igtf",
                "format": "number",
            },
        )
        return fields

    def purchase_book_fields(self):
        fields = super().purchase_book_fields()
        fields.append(
            {
                "name": "IGTF",
                "field": "igtf",
                "format": "number",
            },
        )
        return fields

    def _fields_sale_book_line(self, move, taxes):
        multiplier = -1 if move.move_type == "out_refund" else 1
        is_igtf = bool(move.alter_bi_igtf > 0)
        fields = super()._fields_sale_book_line(move, taxes)
        igtf = (move.tax_totals["igtf"]["foreign_igtf_amount"]) if is_igtf else 0
        if fields:
            fields |= {"igtf": igtf * multiplier,}
        return fields

    def _fields_purchase_book_line(self, move, taxes):
        multiplier = -1 if move.move_type == "in_refund" else 1
        is_igtf = bool(move.alter_bi_igtf > 0)
        fields = super()._fields_purchase_book_line(move, taxes)
        igtf = (move.tax_totals["igtf"]["foreign_igtf_amount"]) if is_igtf else 0
        if fields:
            fields |= {"igtf": igtf * multiplier,}
        return fields
    
    def _get_sale_book_field_groups(self):
        sale_groups = super()._get_sale_book_field_groups()

        igtf_fields = []

        if not self.env.company.not_show_igtf_sale_order:
            igtf_fields.append(
                {"name": "Igtf", "field": "igtf", "format": "number"},
            )

        if igtf_fields:
            sale_groups.append({
                'header': 'IGTF', 
                'fields': igtf_fields
            })

        return sale_groups
    
    def _get_purchase_book_field_groups(self):
        purchase_groups = super()._get_purchase_book_field_groups()

        igtf_fields = []

        if not self.env.company.not_show_igtf_purchase_order:
            igtf_fields.append(
                {"name": "Igtf", "field": "igtf", "format": "number"},
            )

        if igtf_fields:
            purchase_groups.append({
                'header': 'IGTF',
                'fields': igtf_fields
            })

        return purchase_groups