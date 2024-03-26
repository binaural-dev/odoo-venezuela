# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import json
import logging
import time
from odoo import models, fields
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

_logger = logging.getLogger("Shopify Order Queue Line")


class ShopifyOrderDataQueueLineEpt(models.Model):
    _name = "shopify.order.data.queue.line.ept"
    _description = "Shopify Order Data Queue Line"

    shopify_order_data_queue_id = fields.Many2one("shopify.order.data.queue.ept",
                                                  ondelete="cascade")
    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance",
                                          help="Order imported from this Shopify Instance.")
    state = fields.Selection([("draft", "Draft"), ("failed", "Failed"), ("done", "Done"),
                              ("cancel", "Cancelled")], default="draft", copy=False)
    shopify_order_id = fields.Char(help="Id of imported order.", copy=False)
    sale_order_id = fields.Many2one("sale.order", copy=False,
                                    help="Order created in Odoo.")
    order_data = fields.Text(help="Data imported from Shopify of current order.", copy=False)

    customer_name = fields.Text(help="Shopify Customer Name", copy=False)

    customer_email = fields.Text(help="Shopify Customer Email", copy=False)

    processed_at = fields.Datetime(help="Shows Date and Time, When the data is processed",
                                   copy=False)
    shopify_order_common_log_lines_ids = fields.One2many("common.log.lines.ept",
                                                         "shopify_order_data_queue_line_id",
                                                         help="Log lines created against which line.")
    name = fields.Char(help="Order Name")

    def create_order_queue_line(self, order_dict, instance, order_data, customer_name, customer_email, order_queue_id):
        """
        Creates order data queue line from order data.
        :param order_dict: The response of order in the dictionary.
        :param order_data: The response of order in dump data.
        :param order_queue_id: Record of order queue.
        @author: Maulik Barad on Date 10-Sep-2020.
        """
        instance.connect_in_shopify()
        order_data_queue_line_obj = self.env["shopify.order.data.queue.line.ept"]
        # get transaction data call api
        result = []
        transactions = []
        if len(order_dict.get('payment_gateway_names')) >= 1:
            try:
                transactions = shopify.Transaction().find(order_id=order_dict.get('id'))
            except ClientError as error:
                if hasattr(error,
                           "response") and error.response.code == 429 and error.response.msg == "Too Many Requests":
                    time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                    transactions = shopify.Transaction().find(order_id=order_dict.get('id'))
            for transaction in transactions:
                transaction_dict = transaction.to_dict()
                result.append(transaction_dict)
        order_data.update({'transaction': result})

        # get fulfillment data call api
        # shopify_order = shopify.Order().find(order_dict.get('id'))
        # fulfillment_data = shopify_order.get('fulfillment_orders')
        # new_order_data.update({'fulfillment_data': fulfillment_data})

        order_data = json.dumps(order_data)
        existing_data = order_data_queue_line_obj.search(
            [('shopify_order_id', '=', order_dict.get('id')), ('shopify_instance_id', '=', instance.id),
             ('state', 'in', ['draft', 'failed']), ('shopify_order_data_queue_id.is_action_require', '=', False)])
        existing_queue = existing_data.shopify_order_data_queue_id
        order_queue_line_vals = {"shopify_order_id": order_dict.get("id", False),
                                 "shopify_instance_id": instance.id,
                                 "order_data": order_data,
                                 "name": order_dict.get("name", ""),
                                 "customer_name": customer_name,
                                 "customer_email": customer_email,
                                 "shopify_order_data_queue_id": order_queue_id.id}
        if not existing_data:
            self.create(order_queue_line_vals)
        else:
            existing_data.write({"order_data": order_data,
                                 "state": 'draft',
                                 'shopify_order_data_queue_id': existing_queue.id})
            if not existing_queue.order_data_queue_line_ids:
                existing_queue.unlink()
        return True

    def create_order_data_queue_line(self, orders_data, instance, queue_type, created_by="import"):
        """
        This method used to create order data queue lines. It creates new queue after 50 order queue lines.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 06/11/2019.
        Task Id : 157350
        """
        count = 0
        order_queue = False
        need_to_create_queue = True
        orders_data.reverse()
        order_queue_list = []
        fulfillment_data = []
        is_new_order = bool(self._context.get('is_new_order'))
        queue_type_is_buy_with_prime = False
        for order in orders_data:
            if queue_type != 'shipped' and instance.is_delivery_multi_warehouse:
                try:
                    fulfillment_data = order.get('fulfillment_orders')
                except ClientError as error:
                    if hasattr(error,
                               "response") and error.response.code == 429 and error.response.msg == "Too Many Requests":
                        time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                        fulfillment_data = order.get('fulfillment_orders')
            if created_by == "webhook" and not is_new_order:
                order_queue, need_to_create_queue = self.search_webhook_order_queue(created_by, instance, order,
                                                                                    queue_type, need_to_create_queue)
            elif not is_new_order:
                order = order.to_dict()

            if need_to_create_queue:
                order_queue = self.shopify_create_order_queue(instance, queue_type, created_by)
                order_queue_list.append(order_queue.id)
                message = "Order Queue Created %s" % ', '.join(order_queue.mapped('name'))
                if self.env.context.get('queue_created_by'):
                    self.generate_simple_notification(message)
                self._cr.commit()
                need_to_create_queue = False
                _logger.info(message)

            data = json.loads(json.dumps(order))
            if instance.import_buy_with_prime_shopify_order:
                queue_type_is_buy_with_prime = any(
                    buy_with_prime_tag.name in data.get("tags") for buy_with_prime_tag in
                    instance.buy_with_prime_tag_ids)
            data.update({'fulfillment_data': fulfillment_data, "buy_with_prime": queue_type_is_buy_with_prime})
            customer_name, customer_email = self.get_customer_name_and_email(order)
            self.create_order_queue_line(order, instance, data, customer_name, customer_email, order_queue)
            if created_by == "webhook" and len(order_queue.order_data_queue_line_ids) >= 50:
                order_queue.order_data_queue_line_ids.process_import_order_queue_data(update_order=True)

            count += 1
            if count == 50:
                count = 0
                need_to_create_queue = True
        if order_queue and not order_queue.order_data_queue_line_ids:
            order_queue.unlink()
            order_queue_list.remove(order_queue.id)

        return order_queue_list

    def search_webhook_order_queue(self, created_by, instance, order, queue_type, need_to_create_queue):
        """ This method is used to search the webhook order queue.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 27 October 2020 .
            Task_id: 167537
        """
        shopify_order_queue_obj = self.env["shopify.order.data.queue.ept"]

        order_queue = shopify_order_queue_obj.search(
            [("created_by", "=", created_by), ("state", "=", "draft"), ("shopify_instance_id", "=", instance.id),
             ("queue_type", "=", queue_type), ('is_action_require', '=', False)], limit=1)
        if order_queue:
            message = "Order %s added into Order Queue %s." % (order.get("name"), order_queue.name)
            need_to_create_queue = False
            _logger.info(message)
        return order_queue, need_to_create_queue

    def generate_simple_notification(self, message):
        """ This method is used to display simple notification while the opration wizard
            opration running in the backend.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
        """
        bus_bus_obj = self.env["bus.bus"]
        bus_bus_obj._sendone(self.env.user.partner_id, 'simple_notification',
                             {"title": "Shopify Connector",
                              "message": message, "sticky": False, "warning": True})

    def get_customer_name_and_email(self, order):
        """ This method is used to search the customer name and email from the order response.
            :param order: Response of the order.
            @return: customer_name, customer_emailcreate_order_data_queue_line
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
            Task_id: 167537
        """
        try:
            customer_data = order.get("customer")
            customer_name = "%s %s" % (customer_data.get("first_name"),
                                       customer_data.get("last_name"))
            customer_email = customer_data.get("email")
            if customer_name == "None None":
                customer_name = customer_data.get("default_address").get("name")
        except:
            customer_name = False
            customer_email = False

        return customer_name, customer_email

    def shopify_create_order_queue(self, instance, queue_type, created_by="import"):
        """
        This method is used to create a record of the order queue.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 11/11/2019.
        """
        order_queue_vals = {
            "shopify_instance_id": instance and instance.id or False,
            "created_by": created_by,
            "queue_type": queue_type,
        }

        return self.env["shopify.order.data.queue.ept"].create(order_queue_vals)

    def auto_import_order_queue_data(self):
        """
        This method is used to find order queue which queue lines have state in draft and is_action_require is False.
        If cronjob has tried more than 3 times to process any queue then it marks that queue has need process
        to manually. It will be called from auto queue process cron.
        @author: Haresh Mori @Emipro Technologies Pvt.Ltd on date 07/10/2019.
        Task Id : 157350
        """
        shopify_order_queue_obj = self.env["shopify.order.data.queue.ept"]
        order_queue_ids = []

        self.env.cr.execute(
            """update shopify_order_data_queue_ept set is_process_queue = False where is_process_queue = True""")
        self._cr.commit()

        query = """select queue.id
                from shopify_order_data_queue_line_ept as queue_line
                inner join shopify_order_data_queue_ept as queue on queue_line.shopify_order_data_queue_id = queue.id
                where queue_line.state='draft' and queue.is_action_require = 'False'
                ORDER BY queue_line.create_date ASC"""
        self._cr.execute(query)
        order_queue_list = self._cr.fetchall()
        if not order_queue_list:
            return True

        for result in order_queue_list:
            if result[0] not in order_queue_ids:
                order_queue_ids.append(result[0])

        queues = shopify_order_queue_obj.browse(order_queue_ids)
        self.filter_order_queue_lines_and_post_message(queues)

    def filter_order_queue_lines_and_post_message(self, queues):
        """
        This method is used to post a message if the queue is process more than 3 times otherwise
        it calls the child method to process the order queue line.
        :param queues: Record of the order queues.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 16 October 2020 .
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        start = time.time()
        order_queue_process_cron_time = queues.shopify_instance_id.get_shopify_cron_execution_time(
            "shopify_ept.process_shopify_order_queue")

        for queue in queues:
            order_data_queue_line_ids = queue.order_data_queue_line_ids.filtered(lambda x: x.state == "draft")

            # For counting the queue crashes and creating schedule activity for the queue.
            queue.queue_process_count += 1
            if queue.queue_process_count > 3:
                queue.is_action_require = True
                note = "<p>Need to process this order queue manually.There are 3 attempts been made by " \
                       "automated action to process this queue,<br/>- Ignore, if this queue is already processed.</p>"
                queue.message_post(body=note)
                if queue.shopify_instance_id.is_shopify_create_schedule:
                    common_log_line_obj.create_crash_queue_schedule_activity(queue, "shopify.order.data.queue.ept",
                                                                             note)
                continue

            self._cr.commit()
            order_data_queue_line_ids.process_import_order_queue_data()
            if time.time() - start > order_queue_process_cron_time - 60:
                return True

    def process_import_order_queue_data(self, update_order=False):
        """This method processes order queue lines.
            :param update_order: It is used for webhook. While we receive update order webhook response and it
            creates a queue and when auto cron job processing at that time it checks to need to update values in
            existing order if updte_order is True then it will perform opration as received response of order,
            If the update order is False then it will continue order and queue mark as done.
            @author: Haresh Mori @Emipro Technologies Pvt.Ltd on date 07/10/2019.
            Task Id : 157350
        """
        sale_order_obj = self.env["sale.order"]

        queue_id = self.shopify_order_data_queue_id if len(self.shopify_order_data_queue_id) == 1 else False
        if queue_id:
            instance = queue_id.shopify_instance_id
            if not instance.active:
                _logger.info("Instance %s is not active.", instance.name)
                return True

            queue_id.is_process_queue = True
            # Below two line used for When the update order webhook calls.
            if update_order or queue_id.created_by == "webhook":
                created_by = 'Webhook'
                sale_order_obj.update_shopify_order(self, created_by, instance)
            else:
                sale_order_obj.import_shopify_orders(self, instance)
            queue_id.write({'is_process_queue': False})

            if instance.is_shopify_create_schedule:
                queue_id.create_schedule_activity(queue_id)
