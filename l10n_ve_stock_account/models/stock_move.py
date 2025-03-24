from odoo import models
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_line_values(self, use_foreign_currency=False):
        """
        Calculate and return all relevant values for a stock move line, including:
        - Quantity
        - Discount (percentage)
        - Discount amount
        - Tax (percentage)
        - Tax amount
        - Subtotal (before discount and tax)
        - Total (after discount and tax)

        Args:
            use_foreign_currency (bool): If True, use the foreign currency (VEF) for calculations.
                                         If False, use the default currency.

        Returns:
            dict: A dictionary containing the calculated values.
        """
        self.ensure_one()

        price_unit = (
            (
                self.sale_line_id.foreign_price
                if use_foreign_currency
                else self.sale_line_id.price_unit
            )
            if self.sale_line_id
            else 0.0
        )

        quantity = self.quantity or 0.0
        discount = self.sale_line_id.discount or 0.0
        tax = self.sale_line_id.tax_id.amount or 0.0

        subtotal = price_unit * quantity

        discount_amount = subtotal * (discount / 100) if discount else 0.0

        subtotal_after_discount = subtotal - discount_amount

        tax_amount = subtotal_after_discount * (tax / 100) if tax else 0.0


        total_with_tax = subtotal_after_discount + tax_amount

        return {
            "quantity": quantity,
            "discount_percentage": discount,
            "discount_amount": discount_amount,
            "tax_percentage": tax,
            "tax_amount": tax_amount,
            "subtotal": subtotal,
            "subtotal_after_discount": subtotal_after_discount,
            # "": total,
            "total_with_tax": total_with_tax,
        }
