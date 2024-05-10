# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class StockPicking(models.Model):
    """Inhetit the model to add the fields in this model related to connector"""
    _inherit = "stock.picking"

    updated_in_shopify = fields.Boolean(default=False)
    is_shopify_delivery_order = fields.Boolean("Shopify Delivery Order", default=False)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Shopify Instance")
    is_cancelled_in_shopify = fields.Boolean("Is Cancelled In Shopify ?", default=False, copy=False,
                                             help="Use this field to identify shipped in Odoo but cancelled in Shopify")
    is_manually_action_shopify_fulfillment = fields.Boolean("Is Manually Action Required ?", default=False, copy=False,
                                                            help="Those orders which we may fail update fulfillment "
                                                                 "status, we force set True and use will manually take "
                                                                 "necessary actions")
    shopify_fulfillment_id = fields.Char(string='Shopify Fulfillment Id')

    def manually_update_shipment(self):
        """
        This is used to manually update order fulfillment and tracking reference details to Shopify store.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 15 November 2021 .
        Task_id: 179263 - Analysis : Export order status
        """
        picking = self
        order_id = picking.sale_id if picking.sale_id else False

        self.env['sale.order'].with_context(order_id=order_id).update_order_status_in_shopify(self.shopify_instance_id,
                                                                                              picking_ids=picking)
        return True
