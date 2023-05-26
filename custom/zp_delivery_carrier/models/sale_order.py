import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def set_delivery_line(self, carrier, amount):
        date_rate = fields.Date.context_today(self)
        if date_rate > carrier.date_rate:
            carrier.date_rate = date_rate

        res = super().set_delivery_line(carrier, amount)
        return res