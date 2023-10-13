import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    group_product_available_quantity_on_sale = fields.Boolean()
    use_main_warehouse = fields.Boolean()
    main_warehouse_id = fields.Many2one("stock.warehouse")
    not_allow_sell_products = fields.Boolean(
        "Dont allow sell products without quantity", default=False
    )
