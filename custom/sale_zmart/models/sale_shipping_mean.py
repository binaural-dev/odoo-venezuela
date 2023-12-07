from odoo import fields, models


class SaleShippingMean(models.Model):
    _name = "sale.shipping.mean"
    _description = "Sale Shipping Mean"

    name = fields.Char(require=True)
