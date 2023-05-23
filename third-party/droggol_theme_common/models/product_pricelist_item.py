# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models


class PricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    dr_offer_msg = fields.Char('Offer Message', default='Hurry Up! Limited time offer.', translate=True)
    dr_offer_finish_msg = fields.Char('Offer Finish Message', default='Offer Finished.', translate=True)
