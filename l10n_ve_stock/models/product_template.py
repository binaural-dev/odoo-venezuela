import logging
import re
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from collections import defaultdict

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    quantity = fields.Float(
        compute="_compute_available_quantity",
        help="The Availability of the product to sell.",
        digits="Product Unit of Measure",
        store=True,
    )

    free_qty = fields.Float(
        'Free To Use Quantity', 
        compute='_compute_free_qty', 
        search='_search_free_qty', 
        compute_sudo=False, 
        digits='Product Unit of Measure'
    )

    alternate_code = fields.Char(
        string="Alternate Code",
        help="Alternate code for the product",
    )
    physical_location_id = fields.Many2one(
        "stock.location",
        string="Physical Location",
        default=lambda self: self.env.company.main_warehouse_id.lot_stock_id.id,
        domain=[("usage", "=", "internal")],
        tracking=True,
    )

    priority_location = fields.Integer(
        string="Priority", related="physical_location_id.priority", store=True
    )

    price_with_tax = fields.Float(compute="_compute_prices_with_tax")
    price_without_tax = fields.Float(compute="_compute_prices_with_tax")

    liters_per_unit = fields.Float(digits="Stock Weight")

    lock_internal_reference_on_moves = fields.Boolean(
        string="Bloquear referencia interna con movimientos",
        compute="_compute_lock_internal_reference_on_moves",
        inverse="_set_lock_internal_reference_on_moves",
        store=True,
        help=(
            "Si está activo, la referencia interna (código) no podrá "
            "modificarse una vez que el producto (siendo almacenable) tenga "
            "movimientos de inventario ya validados (estado 'Hecho'). Un "
            "pedido de compra o venta confirmado, sin la transferencia "
            "asociada validada todavía, no cuenta como movimiento."
        ),
    )

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        # Maldito Raiver e.e
        return True

    @api.constrains("list_price")
    def _check_list_price(self):

        if self.env.context.get('install_mode'):
            return

        for product in self:
            if product.list_price <= 0:
                raise ValidationError(_("Price cannot be negative or zero."))

    def write(self, vals):
        # default_code and lock_internal_reference_on_moves are both stored
        # fields with their own inverse (_set_default_code on the core side,
        # _set_lock_internal_reference_on_moves here), so Odoo runs them as
        # separate write() calls on the variant, in vals key order. In the
        # resolved form arch, default_code renders before the toggle, so it
        # always arrives first in vals - meaning product.product.write()'s
        # own same-write guard (which reads
        # vals.get("lock_internal_reference_on_moves", ...)) never sees the
        # new toggle value, only the variant's still-locked stored one.
        # Propagate the toggle to the variants directly, before super()
        # triggers any inverse, so unlocking and fixing default_code in the
        # same save always sees the intended state regardless of key order.
        if "lock_internal_reference_on_moves" in vals and "default_code" in vals:
            self.product_variant_ids.write(
                {"lock_internal_reference_on_moves": vals["lock_internal_reference_on_moves"]}
            )

        res = super().write(vals)
        if "taxes_id" in vals:
            self._validate_single_sale_tax()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Always validate after creation because default taxes can come from multiple sources
        records._validate_single_sale_tax()
        return records

    def _validate_single_sale_tax(self):
        for product in self:
            taxes_by_company = defaultdict(int)
            for tax in product.taxes_id.sudo():
                taxes_by_company[tax.company_id] += 1
                if taxes_by_company[tax.company_id] > 1:
                    raise ValidationError(_("This product must have only one tax."))   

    @api.depends("list_price")
    def _compute_prices_with_tax(self):
        for product in self:
            if not product.taxes_id:
                product.price_with_tax = product.list_price
                product.price_without_tax = product.list_price
                continue
            taxes = product.taxes_id.compute_all(
                product.list_price, product.currency_id, 1, product=product
            )
            product.price_with_tax = taxes["total_included"]
            product.price_without_tax = taxes["total_excluded"]

    @api.depends("qty_available","free_qty")
    def _compute_available_quantity(self):
        for product in self:
            current_company = self.env.company
            if not current_company.use_free_qty_odoo:
                stock_quant = self.env["stock.quant"].search(
                    [
                        ("product_tmpl_id", "=", product.id),
                        ("on_hand", "=", True),
                        ("product_tmpl_id.type", "!=", "service"),
                    ]
                )
                quantity_available = 0.0
                for quant in stock_quant:
                    if (
                        quant.warehouse_id.lot_stock_id == quant.location_id
                        or quant.warehouse_id.lot_stock_id == quant.location_id.location_id
                    ):
                        quantity_available += quant.available_quantity
                product.quantity = quantity_available if quantity_available >= 0 else 0
                continue
            product.quantity = product.free_qty

    @api.depends('product_variant_ids.free_qty')
    def _compute_free_qty(self):
        for template in self:
            free_qty = 0
            for p in template.product_variant_ids:
                free_qty += p.free_qty
            template.free_qty = free_qty

    def _search_free_qty(self, operator, value):
        domain = [('free_qty', operator, value)]
        product_variant_query = self.env['product.product'].sudo()._search(domain)
        return [('product_variant_ids', 'in', product_variant_query)]

    @api.depends("product_variant_ids.lock_internal_reference_on_moves")
    def _compute_lock_internal_reference_on_moves(self):
        self._compute_template_field_from_variant_field(
            "lock_internal_reference_on_moves", default=True
        )

    def _set_lock_internal_reference_on_moves(self):
        self._set_product_variant_field("lock_internal_reference_on_moves")
