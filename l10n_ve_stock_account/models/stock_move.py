from odoo import models, api, fields,Command
from odoo.tools.misc import formatLang
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    qty_return = fields.Float(string="Quantity Return", compute="_compute_qty_return",store=True,default=0.0)

    @api.depends("returned_move_ids")
    def _compute_qty_return(self):
        for line in self:
            line.qty_return = sum(line.returned_move_ids.mapped("quantity"))


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

        if not self.sale_line_id:
            return {
                "quantity": self.quantity or 0.0,
                "discount_percentage": 0.0,
                "discount_amount": 0.0,
                "tax_percentage": 0.0,
                "tax_amount": 0.0,
                "subtotal": 0.0,
                "subtotal_after_discount": 0.0,
                "price_unit": 0.0,
                "total_with_tax": 0.0,
            }

        price_unit = self.price_unit_ves_for_dispatch_guide()

        quantity = self.quantity or 0.0
        discount = self.sale_line_id.discount or 0.0
        tax = self.sale_line_id.tax_ids.amount or 0.0

        subtotal = price_unit * quantity

        discount_amount = subtotal * (discount / 100) if discount else 0.0

        subtotal_after_discount = subtotal - discount_amount

        tax_amount = subtotal_after_discount * (tax / 100) if tax else 0.0

        total_with_tax = subtotal_after_discount + tax_amount

        currency = self.env.company.currency_id

        return {
            "quantity": quantity,
            "discount_percentage": discount,
            "discount_amount": formatLang(
                self.env, discount_amount, currency_obj=currency
            ),
            "tax_percentage": tax,
            "tax_amount": formatLang(self.env, tax_amount, currency_obj=currency),
            "subtotal": formatLang(self.env, subtotal, currency_obj=currency),
            "subtotal_after_discount": formatLang(
                self.env, subtotal_after_discount, currency_obj=currency
            ),
            "price_unit": formatLang(self.env, price_unit, currency_obj=currency),
            "total_with_tax": formatLang(
                self.env, total_with_tax, currency_obj=currency
            ),
        }

    def price_unit_ves_for_dispatch_guide(self):
        """
        Convert the unit price of the sale order line to VES (Venezuelan Bolívar) for use in the dispatch guide format.

        This method ensures that the unit price is always expressed in the company's currency (VES),
        regardless of the original currency of the sale order line. The conversion date depends on the
        'indexed_dispatch_guide' flag:
        - If enabled, the conversion uses the picking's done date.
        - If disabled, the conversion uses the sale order's order date.

        Returns:
            float: The unit price converted to VES for the dispatch guide.
        """
        self.ensure_one()
        if not self.sale_line_id:
            return 0.0

        currency = (
            self.sale_line_id.currency_id or self.sale_line_id.order_id.currency_id
        )

        if currency == self.env.company.currency_id:
            return self.sale_line_id.price_unit

        if (
            self.company_id.indexed_dispatch_guide
            or self.env.company.indexed_dispatch_guide
        ):
            date = self.picking_id.date_done
        else:
            date = self.sale_line_id.order_id.date_order

        ves_price_unit = currency._convert(
            self.sale_line_id.price_unit,
            self.env.company.currency_id,
            self.env.company,
            date,
        )

        return ves_price_unit
    
    def _create_account_move(self):
        """ Create account move for specific location or analytic.
            This function is a override of the original function to add the donation logic.
        """
        aml_vals_list = []
        move_to_link = set()
        company_partner = self.env.company.partner_id
        
        is_donation = any(move.scrap_id and move.scrap_id.is_donation for move in self)
        
        for move in self:
            if move._should_create_account_move():
                aml_vals = move._get_account_move_line_vals()
                if is_donation:
                    for val in aml_vals:
                        val["partner_id"] = company_partner.id
                aml_vals_list += aml_vals
                move_to_link.add(move.id)
                
        if not aml_vals_list:
            return self.env['account.move']
            
        move_vals = {
            "journal_id": self.company_id.account_stock_journal_id.id,
            "line_ids": [Command.create(aml_vals) for aml_vals in aml_vals_list],
            "date": self.env.context.get("force_period_date") or fields.Date.context_today(self),
        }
        
        if is_donation:
            reasons = [', '.join(m.scrap_id.scrap_reason_tag_ids.mapped('name')) 
                       for m in self if m.scrap_id and m.scrap_id.is_donation and m.scrap_id.scrap_reason_tag_ids]
            ref = ' - '.join(filter(None, reasons))
            
            move_vals.update({
                "is_donation": True,
                "partner_id": company_partner.id,
                "ref": ref
            })
            
        account_move = self.env["account.move"].sudo().create(move_vals)
        self.env["stock.move"].browse(move_to_link).account_move_id = account_move.id
        account_move._post()
        return account_move