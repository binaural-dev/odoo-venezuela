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
