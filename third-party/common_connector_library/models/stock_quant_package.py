# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'

    tracking_no = fields.Char("Additional Reference", help="This field is used for storing the tracking number.")
