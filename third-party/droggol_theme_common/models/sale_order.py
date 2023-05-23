# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        values = super()._cart_update(product_id=product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs)
        if self.website_id and not self.website_id._dr_has_b2b_access():
            for line in self.order_line:
                new_val = super()._cart_update(product_id=line.product_id.id, line_id=line.id, add_qty=-1, set_qty=0, **kwargs)
                values.update(new_val)
        return values

    def _get_free_delivery_details(self):
        self.ensure_one()
        # We need website_sale_delivery to be installed
        if hasattr(self, '_get_delivery_methods') and not self.only_services:
            valid_methods = self._get_delivery_methods().filtered(lambda x: x.free_over).sorted('amount')
            if valid_methods:
                free_over = valid_methods[0].amount
                order_amount = self._compute_amount_total_without_delivery()
                return {
                    'free_over': free_over,
                    'order_amount': order_amount,
                    'remaining_amount': free_over - order_amount,
                    'progress': order_amount * 100 / free_over,
                }
        return False
