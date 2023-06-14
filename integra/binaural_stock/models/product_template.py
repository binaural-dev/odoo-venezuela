import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

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

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        # Maldito Raiver e.e
        return True

    @api.depends("qty_available", "outgoing_qty")
    def _compute_available_quantity(self):
        for product in self:
            variants_free = product.product_variant_ids.mapped("free_qty")
            total_available: float = sum(variants_free)
            product.update({"quantity": total_available})
