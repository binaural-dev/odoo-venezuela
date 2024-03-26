# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    on_time_shipping = fields.Float("On Time Shipping Days", default=0)
