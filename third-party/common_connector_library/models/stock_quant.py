# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging
from odoo import models

logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def create_inventory_adjustment_ept(self, product_qty_data, location_id, auto_apply=False, name=""):
        """ This method is used to create or update product inventory.
            @param product_qty_data: Dictionary with product and it's quantity. like {'product_id':Qty,52:20, 53:60, 89:23}
            @param location_id : Location
            @param auto_apply: Pass true if automatically apply quant.
            @param name: set name in inventory adjustment name
        """
        quant_list = self.env['stock.quant']
        if product_qty_data and location_id:
            for product_id, product_qty in product_qty_data.items():
                val = self.prepare_vals_for_inventory_adjustment(location_id, product_id, product_qty)
                logger.info("Product ID: %s and its Qty: %s" % (product_id, product_qty))
                quant_list += self.with_context(inventory_mode=True).create(val)
            if auto_apply and quant_list:
                quant_list.filtered(
                    lambda x: x.product_id.tracking not in ['lot', 'serial'] and x.product_id.detailed_type not in [
                        'service', 'consu']).with_context(
                    inventory_name=name).action_apply_inventory()
        return quant_list

    def prepare_vals_for_inventory_adjustment(self, location_id, product_id, product_qty):
        """ This method is use to prepare a vals for the inventory adjustment.
            @param location_id: Browsable record of location.
            @param product_id: Id of product.
            @param product_qty: Quantity of product.
        """
        return {'location_id': location_id.id,
                'product_id': product_id,
                'inventory_quantity': product_qty}
