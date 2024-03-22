# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .. import shopify

_logger = logging.getLogger("Shopify Webhook")

class ShopifyWebhookEpt(models.Model):
    _name = "shopify.webhook.ept"
    _description = 'Shopify Webhook'

    state = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], default='inactive')
    webhook_name = fields.Char(string='Name')
    webhook_action = fields.Selection([('products/create', 'When Product is Created'),
                                       ('products/update', 'When Product is Updated'),
                                       ('products/delete', 'When Product is Delete'),
                                       ('orders/updated', 'When Order is Created/Updated'),
                                       ('customers/create', 'When Customer is Created'),
                                       ('customers/update', 'When Customer is Updated'),
                                       ])
    webhook_id = fields.Char('Webhook Id in Shopify')
    delivery_url = fields.Text("Delivery URL")
    instance_id = fields.Many2one("shopify.instance.ept", string="Webhook created by this Shopify Instance.",
                                  ondelete="cascade")

    @api.model
    def unlink(self):
        """
        This method is used to delete record of webhook in shopify store. Delete receord from here Shopify =>
        Configuration => Instances => Webhooks
        @author: Angel Patel@Emipro Technologies Pvt. Ltd.
        """
        instance = self.instance_id
        if self:
            instance.connect_in_shopify()
            shopify_webhook = shopify.Webhook()
        for record in self:
            if record.webhook_id:
                url = record.get_base_url()
                route = record.get_route()
                try:
                    webhook = shopify_webhook.find(record.webhook_id)
                    address = webhook.address
                    if address[:address.find(route)] == url:
                        webhook.destroy()
                        _logger.info("Deleted %s webhook from Store.", record.webhook_action)
                except:
                    raise UserError(_("Something went wrong while deleting the webhook."))
            _logger.info("Deleted %s webhook from Odoo.", record.webhook_action)
        unlink_main = super(ShopifyWebhookEpt, self).unlink()
        self.deactivate_auto_create_webhook(instance)
        return unlink_main

    def deactivate_auto_create_webhook(self, instance):
        """ This method is used to for deactivate the webhook for shopify configuration if webhook are delete from
            shopify instance.
        """
        _logger.info("deactivate_auto_create_webhook process start")
        product_webhook = instance.list_of_topic_for_webhook('product')
        customer_webhook = instance.list_of_topic_for_webhook('customer')
        order_webhook = instance.list_of_topic_for_webhook('order')
        all_webhook_action = self.search([('instance_id', '=', instance.id)]).mapped('webhook_action')
        if instance.create_shopify_products_webhook:
            result = any(elem in product_webhook for elem in all_webhook_action)
            if not result:
                instance.write({'create_shopify_products_webhook': False})
                _logger.info("Inactive create_shopify_products_webhook from the %s instance", instance.name)
        if instance.create_shopify_customers_webhook:
            result = any(elem in customer_webhook for elem in all_webhook_action)
            if not result:
                instance.write({'create_shopify_customers_webhook': False})
                _logger.info("Inactive create_shopify_customers_webhook from the %s instance", instance.name)
        if instance.create_shopify_orders_webhook:
            result = any(elem in order_webhook for elem in all_webhook_action)
            if not result:
                instance.write({'create_shopify_orders_webhook': False})
                _logger.info("Inactive create_shopify_orders_webhook from the %s instance", instance.name)

    @api.model_create_multi
    def create(self, values):
        """
        This method is used to create a webhook.
        @author: Angel Patel@Emipro Technologies Pvt. Ltd.
        """
        for val in values:
            available_webhook = self.search(
                [('instance_id', '=', val.get('instance_id')), ('webhook_action', '=', val.get('webhook_action'))],
                limit=1)
            if available_webhook:
                raise UserError(_('Webhook is already created with the same action.'))

            result = super(ShopifyWebhookEpt, self).create(val)
            result.get_webhook()
        return result

    def get_route(self):
        """
        Gives delivery URL for the webhook as per the Webhook Action.
        @author: Haresh Mori on Date 9-Jan-2020.
        """
        webhook_action = self.webhook_action
        if webhook_action == 'products/update':
            route = "/shopify_odoo_webhook_for_product_update"
        elif webhook_action == 'products/create':
            route = "/shopify_odoo_webhook_for_product_create"
        elif webhook_action == 'products/delete':
            route = "/shopify_odoo_webhook_for_product_delete"
        elif webhook_action == 'orders/updated':
            route = "/shopify_odoo_webhook_for_orders_partially_updated"
        elif webhook_action == 'customers/create':
            route = "/shopify_odoo_webhook_for_customer_create"
        elif webhook_action == 'customers/update':
            route = "/shopify_odoo_webhook_for_customer_update"
        return route

    def get_webhook(self):
        """
        Creates webhook in Shopify Store for webhook in Odoo if no webhook is
        there, otherwise updates status of the webhook, if it exists in Shopify store.
        @author: Haresh Mori on Date 9-Jan-2020.
        """
        instance = self.instance_id
        instance.connect_in_shopify()
        route = self.get_route()
        current_url = instance.get_base_url()
        shopify_webhook = shopify.Webhook()
        url = current_url + route
        if url[:url.find(":")] == 'http':
            raise UserError(_("Address protocol http:// is not supported for creating the webhooks."))

        webhook_vals = {"topic": self.webhook_action, "address": url, "format": "json"}
        response = shopify_webhook.create(webhook_vals)
        if response.id:
            new_webhook = response.to_dict()
            self.write({"webhook_id": new_webhook.get("id"), 'delivery_url': url, 'state': 'active'})
        return True
