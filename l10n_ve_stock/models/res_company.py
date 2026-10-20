import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    group_product_available_quantity_on_sale = fields.Boolean()

    use_main_warehouse = fields.Boolean()

    main_warehouse_id = fields.Many2one("stock.warehouse")

    change_weight = fields.Boolean()

    use_physical_location = fields.Boolean()

    use_alternate_locations = fields.Boolean()

    physical_relocation_transfer = fields.Boolean(
        string="Generate automatic internal transfer when physical location changes",
        help="When a physical location is replaced by another, generates "
        "and validates an internal transfer that carries the stock from "
        "the old location to the new one. Only applies to the inventory "
        "manager.",
    )

    use_free_qty_odoo = fields.Boolean()

    # not_allow_sell_products = fields.Boolean(

    validate_without_product_quantity = fields.Boolean(
        "Allow Validate Without Product Quantity", default=False
    )
    limit_product_qty_out = fields.Integer()

    not_allow_negative_inventory_adjustments = fields.Boolean()

    allow_scrap_more_than_available = fields.Boolean()

    not_allow_scrap_more_than_what_was_manufactured = fields.Boolean()

    not_allow_negative_stock_movement = fields.Boolean()
