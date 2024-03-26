# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger("Shopify Controller")


class Main(http.Controller):

    @http.route(['/shopify_odoo_webhook_for_product_create', '/shopify_odoo_webhook_for_product_update',
                 '/shopify_odoo_webhook_for_product_delete'], csrf=False,
                auth="public", type="json")
    def create_update_delete_product_webhook(self):
        """
        Route for handling the product create/update/delete webhook of Shopify. This route calls while any new product
        create or update or delete in the Shopify store.
        @author: Dipak Gogiya on Date 10-Jan-2020.
        """
        webhook_route = request.httprequest.path.split('/')[1]  # Here we receive two type of route
        # 1) Update and create product (shopify_odoo_webhook_for_product_update)
        # 2) Delete product (shopify_odoo_webhook_for_product_delete)

        res, instance = self.get_basic_info(webhook_route)

        if not res:
            return

        _logger.info("%s call for product: %s", webhook_route, res.get("title"))

        shopify_template = request.env["shopify.product.template.ept"].sudo().with_context(active_test=False).search(
            [("shopify_tmpl_id", "=", res.get("id")), ("shopify_instance_id", "=", instance.id)], limit=1)

        if webhook_route == 'shopify_odoo_webhook_for_product_create' and shopify_template or res.get("published_at"):
            request.env["shopify.product.data.queue.ept"].sudo().create_shopify_product_queue_from_webhook(res,
                                                                                                           instance)

        if webhook_route == 'shopify_odoo_webhook_for_product_update' and shopify_template or res.get("published_at"):
            request.env["shopify.product.data.queue.ept"].sudo().create_shopify_product_queue_from_webhook(res,
                                                                                                           instance)

        if webhook_route == 'shopify_odoo_webhook_for_product_delete' and shopify_template:
            shopify_template.write({"active": False})
        return

    @http.route(['/shopify_odoo_webhook_for_customer_create', '/shopify_odoo_webhook_for_customer_update'], csrf=False,
                auth="public", type="json")
    def customer_create_or_update_webhook(self):
        """
        Route for handling customer create/update webhook for Shopify. This route calls while new customer create
        or update customer values in the Shopify store.
        @author: Dipak Gogiya on Date 10-Jan-2020.
        """
        webhook_route = request.httprequest.path.split('/')[1]  # Here we receive two type of route
        # 1) Create Customer (shopify_odoo_webhook_for_customer_create)
        # 2) Update Customer(shopify_odoo_webhook_for_customer_update)

        res, instance = self.get_basic_info(webhook_route)
        if not res:
            return
        if res.get("first_name") or res.get("last_name"):
            _logger.info("%s call for Customer: %s", webhook_route,
                         (res.get("first_name") + " " + res.get("last_name")))
            self.customer_webhook_process(res, instance)
        return

    def customer_webhook_process(self, response, instance):
        """
        This method used for call child method of customer create process.
        @author: Maulik Barad on Date 23-Sep-2020.
        """
        process_import_export_model = request.env["shopify.process.import.export"].sudo()
        process_import_export_model.webhook_customer_create_process(response, instance)
        return True

    @http.route("/shopify_odoo_webhook_for_orders_partially_updated", csrf=False, auth="public", type="json")
    def order_create_or_update_webhook(self):
        """
        Route for handling the order update webhook of Shopify. This route calls while new order create
        or update in the Shopify store.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13-Jan-2020.
        """
        res, instance = self.get_basic_info("shopify_odoo_webhook_for_orders_partially_updated")
        sale_order = request.env["sale.order"]
        if not res:
            return

        _logger.info("UPDATE ORDER WEBHOOK call for order: %s", res.get("name"))

        fulfillment_status = res.get("fulfillment_status") or "unfulfilled"
        if sale_order.sudo().search_read([("shopify_instance_id", "=", instance.id),
                                          ("shopify_order_id", "=", res.get("id")),
                                          ("shopify_order_number", "=",
                                           res.get("order_number"))],
                                         ["id"]):
            sale_order.sudo().process_shopify_order_via_webhook(res, instance, True)
        elif fulfillment_status in ["fulfilled", "unfulfilled", "partial"]:
            res["fulfillment_status"] = fulfillment_status
            sale_order.sudo().with_context({'is_new_order': True}).process_shopify_order_via_webhook(res,
                                                                                                     instance)
        return

    def get_basic_info(self, route):
        """
        This method is used to check that instance and webhook are active or not. If yes then return response and
        instance, If no then return response as False and instance.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 10-Jan-2020..
        """
        res = request.get_json_data()
        host = request.httprequest.headers.get("X-Shopify-Shop-Domain")
        instance = request.env["shopify.instance.ept"].sudo().with_context(active_test=False).search(
            [("shopify_host", "ilike", host)], limit=1)

        webhook = request.env["shopify.webhook.ept"].sudo().search([("delivery_url", "ilike", route),
                                                                    ("instance_id", "=", instance.id)], limit=1)

        if not instance.active or not webhook.state == "active":
            _logger.info("The method is skipped. It appears the instance:%s is not active or that "
                         "the webhook %s is not active.", instance.name, webhook.webhook_name)
            res = False
        return res, instance
