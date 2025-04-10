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
    use_free_qty_odoo = fields.Boolean()

    validate_without_product_quantity = fields.Boolean(
        "Allow Validate Without Product Quantity", default=False
    )
