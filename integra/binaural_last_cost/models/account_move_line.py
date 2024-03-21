from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    latest_standard_price = fields.Monetary(compute="_compute_latest_standard_price", store=True)

    update_latest_standard_price = fields.Boolean(
        related="product_id.product_tmpl_id.update_last_cost", readonly=False
    )


    @api.depends("product_id")
    def _compute_latest_standard_price(self):
        for line in self:
            latest_standard_price = line.product_id.latest_standard_price
            line.latest_standard_price = latest_standard_price

    @api.onchange("price_unit")
    def onchange_update_latest_standard_price(self):
        """
        If the price unit is changed, the update_latest_standard_price field is set to True by
        default.
        """
        is_price_unit_greater_than_last_standard_price = self.price_unit > self.latest_standard_price
        self.update_latest_standard_price = is_price_unit_greater_than_last_standard_price