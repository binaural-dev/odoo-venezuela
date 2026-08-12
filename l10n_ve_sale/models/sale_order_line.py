from odoo import api, fields, models, _
import logging
from odoo.exceptions import UserError, ValidationError



_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    foreign_currency_id = fields.Many2one(
        related="order_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="order_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(

        related="order_id.foreign_inverse_rate",
        store=True,

    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )

    invoiced = fields.Boolean(compute="_compute_invoiced", store=True, copy=False)

    

    @api.depends("invoice_lines.move_id.state", "invoice_lines.quantity")
    def _compute_invoiced(self):
        for line in self:
            invoice_lines = line._get_invoice_lines()
            invoiced = invoice_lines and all(
                invoice_line.move_id.move_type == "out_invoice"
                for invoice_line in invoice_lines
            )
            line.invoiced = invoiced

    

    @api.depends("order_id.foreign_inverse_rate")
    def _compute_foreign_inverse_rate(self):
        for record in self:
            valor_orden = record.order_id.foreign_inverse_rate or 0.0
            if record.foreign_inverse_rate != valor_orden:
                record.foreign_inverse_rate = valor_orden

    @api.depends("price_unit", "foreign_inverse_rate", "currency_id",
                  "order_id.foreign_inverse_rate")
    def _compute_foreign_price(self):
        """`foreign_price` is a `Float` with its own "Foreign Product Price"
        precision, not a `Monetary` (see account.move.line in
        l10n_ve_accountant) -- `Monetary` always rounds to the currency's
        precision (2 decimals for VEF) on save regardless of the real unit
        price precision, which would keep the anchored total
        (`amount_total x rate`) from matching the bottom-up sum of the
        lines to the cent.

        The computation itself used to be a plain `price_unit *
        foreign_inverse_rate`. `res.currency._convert` (see l10n_ve_rate)
        has a branch that DIVIDES by `custom_rate` instead of multiplying
        when the document's currency differs from the company's base AND
        that base is USD -- a plain multiply ignores that branch entirely
        and would give a wrong `foreign_price` in that case. Delegating to
        `_convert` (like account.move.line._compute_foreign_price) makes
        both models compute the alterno the exact same way regardless of
        the currency combination. `round=False` preserves "Foreign Product
        Price"'s precision instead of collapsing it to the alterno
        currency's 2 decimals before the field rounds itself with its own
        precision.
        """
        for line in self:
            line.foreign_price = line.currency_id._convert(
                line.price_unit,
                line.foreign_currency_id,
                line.company_id,
                line.order_id.date_order.date() if line.order_id.date_order else fields.Date.today(),
                custom_rate=line.foreign_inverse_rate,
                round=False,
            )

    @api.depends("product_uom_qty", "foreign_price", "discount", "tax_id")
    def _compute_foreign_subtotal(self):
        """Delegates to `tax_id.compute_all(...)` to get the tax-excluded
        amount in the alterno currency (like
        account.move.line._compute_foreign_subtotal), handling
        price-included taxes and rounding methods correctly -- instead of
        a plain multiply that ignored `tax_id` entirely and assumed
        `price_unit` always excludes tax.
        """
        for line in self:
            if not line.product_uom_qty or not line.foreign_price:
                line.foreign_subtotal = 0.0
                continue

            foreign_price_unit_full_precision = line.foreign_price * (
                1 - (line.discount / 100.0)
            )

            if line.tax_id:
                taxes_res = line.tax_id.compute_all(
                    foreign_price_unit_full_precision,
                    quantity=line.product_uom_qty,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.order_partner_id,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
            else:
                line.foreign_subtotal = line.foreign_currency_id.round(
                    foreign_price_unit_full_precision * line.product_uom_qty
                )
            
    def _prepare_invoice_line(self, **optional_values):
       
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        res['foreign_subtotal'] = self.foreign_subtotal
        res['foreign_price'] = self.foreign_price
        res['foreign_inverse_rate'] = self.foreign_inverse_rate
        res['foreign_currency_id'] = self.foreign_currency_id.id
        return res