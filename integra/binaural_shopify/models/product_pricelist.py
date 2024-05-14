from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class Pricelist(models.Model):
    _inherit="product.pricelist"


    def action_set_product_price(self):
        """
        This method sets de product price 
        """
        for rec in self:
            for line in rec.item_ids:
                if line.product_id:
                    line.fixed_price = line.product_id.lst_price