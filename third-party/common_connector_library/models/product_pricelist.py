# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def set_product_price_ept(self, product_id, price, min_qty=1):
        """ Use to Create/Update price in the pricelist.
            @param product_id: Record of product
            @param price: Price of Product.
        """
        pricelist_item_obj = self.env['product.pricelist.item']
        domain = [('pricelist_id', '=', self.id), ('product_id', '=', product_id), ('min_quantity', '=', min_qty)]

        pricelist_item = pricelist_item_obj.search(domain)

        if pricelist_item:
            pricelist_item.write({'fixed_price': price})
        else:
            vals = self.prepre_pricelistitem_vals(product_id, min_qty, price)
            new_record = pricelist_item_obj.new(vals)
            new_record._onchange_product_id()
            new_vals = pricelist_item_obj._convert_to_write(
                {name: new_record[name] for name in new_record._cache})
            pricelist_item = pricelist_item_obj.create(new_vals)
        return pricelist_item

    def prepre_pricelistitem_vals(self, product_id, min_qty, price):
        """ Use to prepare a vals of pricelist item.
            @param : product_id : Product Id
            @param : min_qty : Minimum qty, It always 1
            @param : price : Price of product.
        """
        vals = {
            'pricelist_id': self.id,
            'applied_on': '0_product_variant',
            'product_id': product_id,
            'min_quantity': min_qty,
            'fixed_price': price,
        }
        return vals

    def get_product_price_list_rule(self, product, quantity, partner):
        """ add method for a get price and rule base on given pricelist and product
            added by : Nilam Kubavat at 21st April 2023
        """
        rule = self._get_product_price_rule(product, quantity, partner, date=False, uom_id=product.uom_id.id)
        return rule
