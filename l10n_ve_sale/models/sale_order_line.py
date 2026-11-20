from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round

from .l10n_ve_discount_document import is_discount_applying
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = ["sale.order.line", "l10n_ve.discount.line.mixin"]
    _name = "sale.order.line"

    foreign_currency_id = fields.Many2one(
        related="order_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="order_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="order_id.foreign_inverse_rate", store=True
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

    def _discount_quantity(self):
        return self.product_uom_qty

    def _get_line_discount_type(self, company=None, vals=None):
        order = self.order_id
        if not order and vals and vals.get("order_id"):
            order = self.env["sale.order"].browse(vals["order_id"])
        if order:
            return order._get_doc_discount_type()
        company = company or self.company_id or self.env.company
        return company.discount_type or "percent"

    def _get_effective_discount_percent(self):
        self.ensure_one()
        if self._uses_discount_fixed():
            return self._get_exact_discount_percentage()
        return self.discount or 0.0

    @api.constrains("product_uom_qty")
    def _check_discount_fixed_quantity(self):
        self._check_discount_fixed_not_exceeding_subtotal()

    @api.depends("discount_fixed", "order_id.discount_mode")
    def _compute_amount(self):
        return super()._compute_amount()

    def _check_order_not_locked_by_approval(self, orders=None):
        """The lines of an order waiting for a discount approval are locked."""
        if self.env.su or is_discount_applying(self.env):
            return
        orders = orders if orders is not None else self.order_id
        if any(order.state == "to_approve" for order in orders):
            raise UserError(
                _(
                    "This order is waiting for a discount approval and cannot be "
                    "edited. A discount approver can approve or reject the "
                    "discount, or the order can be cancelled."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_order_not_locked_by_approval(
            self.env["sale.order"].browse([v["order_id"] for v in vals_list if v.get("order_id")])
        )
        for vals in vals_list:
            order = self.env["sale.order"].browse(vals.get("order_id"))
            if order and ("discount" in vals or "discount_fixed" in vals):
                order._discount_guard(vals)
                self._enforce_discount_exclusivity(vals)
        lines = super().create(vals_list)
        lines.order_id._reapply_global_discount()
        if any("discount" in v or "discount_fixed" in v for v in vals_list):
            lines.order_id._evaluate_discount_approval()
        return lines

    def write(self, vals):
        if not set(vals) <= {"state", "invoice_status"}:
            self._check_order_not_locked_by_approval()
        touches_discount = "discount" in vals or "discount_fixed" in vals
        if touches_discount:
            for order in self.order_id:
                order._discount_guard(vals)
        if touches_discount and not is_discount_applying(self.env):
            for line in self:
                line_vals = dict(vals)
                line._enforce_discount_exclusivity(line_vals, company=line.company_id)
                super(SaleOrderLine, line).write(line_vals)
            res = True
        else:
            res = super().write(vals)
        if {"price_unit", "product_uom_qty", "product_id", "display_type"} & set(vals):
            self.order_id._reapply_global_discount()
        if touches_discount and not is_discount_applying(self.env):
            self.order_id._evaluate_discount_approval()
        return res

    def unlink(self):
        self._check_order_not_locked_by_approval()
        orders = self.order_id
        res = super().unlink()
        orders.exists()._reapply_global_discount()
        return res

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if not self.display_type:
            res["discount_fixed"] = (
                self.discount_fixed if self._uses_discount_fixed() else 0.0
            )
        return res

    # override
    @api.depends("product_id", "product_uom_id", "product_uom_qty","order_id.currency_id")
    def _compute_price_unit(self):
        def has_manual_price(line):
            # `line.currency_id` can be False for NewId records
            currency = (
                line.currency_id or
                line.order_id.currency_id
                or line.company_id.currency_id
                or line.env.company.currency_id
            )
            return currency.compare_amounts(line.technical_price_unit, line.price_unit)

        force_recompute = self.env.context.get('force_price_recomputation')
        for line in self:
            # Don't compute the price for deleted lines or lines for which the
            # price unit doesn't come from the product.
            if not line.order_id or line.is_downpayment or line._is_global_discount():
                continue

            # check if the price has been manually set or there is already invoiced amount.
            # if so, the price shouldn't change as it might have been manually edited.
            if (
                (not force_recompute and has_manual_price(line))
                or line.qty_invoiced > 0
                or (line.product_id.expense_policy == 'cost' and line.is_expense)
            ):
                continue
            line = line.with_context(sale_write_from_compute=True)
            if not line.product_uom_id or not line.product_id:
                line.price_unit = 0.0
                line.technical_price_unit = 0.0
            else:
                line._reset_price_unit()
    @api.depends("invoice_lines.move_id.state", "invoice_lines.quantity")
    def _compute_invoiced(self):
        for line in self:
            invoice_lines = line._get_invoice_lines()
            invoiced = invoice_lines and all(
                invoice_line.move_id.move_type == "out_invoice"
                for invoice_line in invoice_lines
            )
            line.invoiced = invoiced

    @api.depends(
        "price_unit",
        "order_id.date_order",
        "order_id.foreign_rate_date",
        "currency_id",
        "company_id",
    )
    def _compute_foreign_price(self):
        for line in self:

            # foreign_rate_date es la fecha de la que salio la tasa de la orden
            # y sobrevive a que el core reescriba date_order al confirmar. Sin
            # esto la linea se recalculaba con la fecha de confirmacion aunque
            # la tasa de la orden estuviera congelada.
            order_date = (
                line.order_id.foreign_rate_date
                or fields.Date.context_today(line, line.order_id.date_order)
            )

            company_currency = line.company_id.currency_id
            foreign_currency = line.company_id.foreign_currency_id
            line_currency = line.currency_id or line.order_id.currency_id or line.company_id.currency_id

            if not line_currency or not foreign_currency:
                line.foreign_price = 0.0
                continue

            if line_currency.id == foreign_currency.id:
                line.foreign_price = line.price_unit
                continue

            # round=False + redondeo a la precision del campo: _convert()
            # redondea por defecto a los decimales de la moneda destino
            # (USD = 2), pero foreign_price usa "Foreign Product Price",
            # cuya precision es configurable.
            # Sin esto un precio unitario pequeño se pierde al convertir, y
            # el valor de la orden no coincide con el de la factura que sale
            # de ella (account.move.line usa el mismo criterio).
            precision = self.env["decimal.precision"].precision_get(
                "Foreign Product Price"
            )
            line.foreign_price = float_round(
                line_currency._convert(
                    line.price_unit,
                    foreign_currency,
                    line.company_id,
                    order_date,
                    round=False,
                ),
                precision_digits=precision,
            )

    @api.depends("product_uom_qty", "foreign_price", "discount", "discount_fixed", "tax_ids")
    def _compute_foreign_subtotal(self):
        """Subtotal en moneda alterna.

        Mismo criterio que account.move.line: cuando hay impuestos se pasa por
        compute_all para que el subtotal sea la base real (descuenta el
        impuesto si va incluido en el precio) y quede redondeado a la moneda
        alterna. Sin impuestos es la multiplicacion directa.
        """
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line._get_effective_discount_percent() / 100.0)
            )
            foreign_subtotal = line_discount_price_unit * line.product_uom_qty

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.product_uom_qty,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.order_id.partner_id,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
            else:
                line.foreign_subtotal = foreign_subtotal

    
    def _prepare_foreign_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            self,
            price_unit=self.foreign_price,
            tax_ids=self.tax_ids,
            quantity=self.product_uom_qty,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id or self.order_id.company_id.currency_id,
            rate=getattr(self.order_id, 'currency_rate', 1.0),
        )
