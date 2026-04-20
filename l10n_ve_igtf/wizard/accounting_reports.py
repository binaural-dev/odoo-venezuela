from datetime import datetime

import xlsxwriter
from odoo import _, api, models
from odoo.osv import expression

import logging

_logger = logging.getLogger(__name__)

class WizardAccountingReports(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    def sale_book_fields(self):
        """
        Extend the Sale Book field definitions to include IGTF columns.

        This method adds two additional numeric columns to the sale book:
            - Bi igtf: IGTF taxable base.
            - Igtf: IGTF tax amount.

        These fields are used when generating the sales accounting report,
        allowing the IGTF information to be displayed and exported.

        Returns:
            list: List of field definitions for the sale book.
        """
        fields = super().sale_book_fields()
        fields.extend(
            [
                # {
                #     "name": "Bi igtf",
                #     "field": "bi_igtf",
                #     "format": "number",
                # },
                {
                    "name": "IGTF",
                    "field": "igtf",
                    "format": "number",
                },
            ]
        )
        return fields

    def purchase_book_fields(self):
        """
        Extend the Purchase Book field definitions to include IGTF columns.

        This method adds two additional numeric columns to the purchase book:
            - Bi igtf: IGTF taxable base.
            - Igtf: IGTF tax amount.

        These fields allow IGTF data to be displayed in purchase accounting
        reports and exported to external formats (e.g., Excel).

        Returns:
            list: List of field definitions for the purchase book.
        """
        fields = super().purchase_book_fields()
        fields.extend(
            [
                # {
                #     "name": "Bi igtf",
                #     "field": "bi_igtf",
                #     "format": "number",
                # },
                {
                    "name": "IGTF",
                    "field": "igtf",
                    "format": "number",
                },
            ]
        )
        return fields

    def _fields_sale_book_line(self, move, taxes):
        """
        Add IGTF values to each Sale Book report line.

        This method injects the IGTF taxable base and IGTF amount into the
        data structure used to render each sales report line.

        The values depend on the currency system:
            - If foreign currency is used, foreign IGTF fields are applied.
            - Otherwise, local currency IGTF fields are used.

        For credit notes (out_refund), the values are inverted using
        a negative multiplier.

        Args:
            move (account.move): The invoice or refund being processed.
            taxes (dict): Tax information associated with the move.

        Returns:
            dict: Updated field values for the sale book line.
        """
        is_check_currency_system = self.currency_system
        fields = super()._fields_sale_book_line(move, taxes)
        multiplier = -1 if move.move_type == "out_refund" else 1
        bi_igtf = move.foreign_bi_igtf if not self.currency_system else move.bi_igtf
        is_igtf = bool(move.alter_bi_igtf > 0)
        igtf = (move.tax_totals["igtf"]["foreign_igtf_amount"]) if is_igtf else 0
        # fields |= {"bi_igtf": bi_igtf,}
        if fields:
            fields |= {"igtf": igtf * multiplier,}

        return fields

    def _fields_purchase_book_line(self, move, taxes):
        """
        Add IGTF values to each Purchase Book report line.

        This method injects the IGTF taxable base and IGTF amount into the
        purchase accounting report structure.

        The applied values depend on the currency configuration:
            - Foreign currency values are used when currency_system is disabled.
            - Local currency values are used otherwise.

        For vendor refunds (in_refund), values are inverted using a
        negative multiplier.

        Args:
            move (account.move): The vendor bill or refund being processed.
            taxes (dict): Tax information associated with the move.

        Returns:
            dict: Updated field values for the purchase book line.
        """
        is_check_currency_system = self.currency_system
        fields = super()._fields_purchase_book_line(move, taxes)
        multiplier = -1 if move.move_type == "in_refund" else 1
        bi_igtf = move.foreign_bi_igtf if not self.currency_system else move.bi_igtf
        is_igtf = bool(move.alter_bi_igtf > 0)
        _logger.info(f"TAX TOTALS IGTF:{move.tax_totals["igtf"]}")
        igtf =  (move.tax_totals["igtf"]["foreign_igtf_amount"]) if is_igtf else 0
        # fields |= {"bi_igtf": bi_igtf,}
        if fields:
            fields |= {"igtf": igtf * multiplier,}

        return fields
    
    def _get_sale_book_field_groups(self):
        """
        Add an IGTF group to the Sale Book report layout.

        This method appends a new column group named 'IGTF' to the sale
        book report, grouping the following fields:
            - Bi igtf
            - Igtf

        This improves the visual organization of IGTF data in the report.

        Returns:
            list: Updated list of field groups for the sale book.
        """
        sale_groups = super()._get_sale_book_field_groups()

        igtf_fields = [
        ]

        # if not self.env.company.not_show_bi_igtf_sale_order:
        #     igtf_fields.append(            
        #         {"name": "Bi igtf", "field": "bi_igtf", "format": "number"},
        #     )

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
        """
        Add an IGTF group to the Purchase Book report layout.

        This method appends a new column group named 'IGTF' to the purchase
        book report, grouping the following fields:
            - Bi igtf
            - Igtf

        This ensures IGTF information is clearly separated and
        visible in the purchase accounting reports.

        Returns:
            list: Updated list of field groups for the purchase book.
        """
        purchase_groups = super()._get_purchase_book_field_groups()

        igtf_fields = [
        ]

        # if not self.env.company.not_show_bi_igtf_purchase_order:
        #     igtf_fields.append(            
        #         {"name": "Bi igtf", "field": "bi_igtf", "format": "number"},
        #     )

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