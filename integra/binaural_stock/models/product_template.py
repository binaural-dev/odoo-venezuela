import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"
    _order = "priority_location asc"

    quantity = fields.Float(
        compute="_compute_available_quantity",
        help="The Availability of the product to sell.",
        digits="Product Unit of Measure",
        store=True,
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

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        # Maldito Raiver e.e
        return True

    @api.constrains("taxes_id")
    def _check_taxes_id(self):
        for product in self:
            if len(product.taxes_id) != 1 and self.env.company.unique_tax:
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

    @api.depends("qty_available")
    def _compute_available_quantity(self):
        for product in self:
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
            product.update({"quantity": quantity_available if quantity_available >= 0 else 0})
