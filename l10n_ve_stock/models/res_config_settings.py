from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    group_product_available_quantity_on_sale = fields.Boolean(
        "Show Available Quantity From All Warehouses",
        related="company_id.group_product_available_quantity_on_sale",
        readonly=False,
        implied_group="l10n_ve_stock.group_product_available_quantity_on_sale",
    )
    use_main_warehouse = fields.Boolean(related="company_id.use_main_warehouse", readonly=False)
    main_warehouse_id = fields.Many2one(
        "stock.warehouse", related="company_id.main_warehouse_id", readonly=False
    )
    change_weight = fields.Boolean(
        related="company_id.change_weight",
        readonly=False,
    )
    use_physical_location = fields.Boolean(
        related="company_id.use_physical_location",
        readonly=False,
    )

    use_free_qty_odoo = fields.Boolean(
        related="company_id.use_free_qty_odoo",
        readonly=False,
    )

    validate_without_product_quantity = fields.Boolean(
        related="company_id.validate_without_product_quantity", readonly=False
    )

    limit_product_qty_out = fields.Integer(string="Limit stock picking product lines", related='company_id.limit_product_qty_out', readonly=False)

    not_allow_negative_inventory_adjustments = fields.Boolean(
        "Not Allow Negative Inventory Adjustments",
        related="company_id.not_allow_negative_inventory_adjustments",
        readonly=False,
    )

    allow_scrap_more_than_available = fields.Boolean(related='company_id.allow_scrap_more_than_available', readonly=False)

    not_allow_scrap_more_than_what_was_manufactured = fields.Boolean(
        "Not Allow Scrap More Than What Was Manufactured",
        related="company_id.not_allow_scrap_more_than_what_was_manufactured",
        readonly=False
    )

    not_allow_negative_stock_movement = fields.Boolean(
        string="Prevent internal movement with negative stock",
        related="company_id.not_allow_negative_stock_movement",
        readonly=False
    )

    