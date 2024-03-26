# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import json
import logging
import time
from datetime import datetime

from odoo import models, fields, api, _

_logger = logging.getLogger("Shopify Customer Queue Line")


class ShopifyCustomerDataQueueLineEpt(models.Model):
    """This model is used to handel the customer data queue line"""
    _name = "shopify.customer.data.queue.line.ept"
    _description = "Shopify Synced Customer Data Line"

    state = fields.Selection([("draft", "Draft"), ("failed", "Failed"), ("done", "Done"),
                              ("cancel", "Cancelled")], default="draft")
    shopify_synced_customer_data = fields.Char(string="Shopify Synced Data")
    shopify_customer_data_id = fields.Text(string="Customer ID")
    synced_customer_queue_id = fields.Many2one("shopify.customer.data.queue.ept",
                                               string="Shopify Customer",
                                               ondelete="cascade")
    last_process_date = fields.Datetime()
    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    common_log_lines_ids = fields.One2many("common.log.lines.ept",
                                           "shopify_customer_data_queue_line_id",
                                           help="Log lines created against which line.")
    name = fields.Char(string="Customer", help="Shopify Customer Name")

    def shopify_create_multi_queue(self, customer_queue_id, customer_ids):
        """
        This method used to call child method for create a customer queue line.
        :param customer_queue_id: Record of the customer queue.
        :param customer_ids: 125 records of customer response.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 23/10/2019.
        :Task ID: 157065
        """
        if customer_queue_id:
            for result in customer_ids:
                result = result.to_dict()
                self.shopify_customer_data_queue_line_create(result, customer_queue_id)
        return True

    def shopify_customer_data_queue_line_create(self, result, customer_queue_id):
        """
        This method used to create a customer queue line.
        :param result:Response of 1 customer.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 13/01/2020.
        """
        synced_shopify_customers_line_obj = self.env["shopify.customer.data.queue.line.ept"]
        name = "%s %s" % (result.get("first_name") or "", result.get("last_name") or "")
        customer_id = result.get("id")
        data = json.dumps(result)
        instance_id = customer_queue_id.shopify_instance_id.id
        existing_customer_data = synced_shopify_customers_line_obj.search(
            [('shopify_customer_data_id', '=', customer_id), ('shopify_instance_id', '=', instance_id),
             ('state', 'in', ['draft', 'failed'])])
        line_vals = {
            "synced_customer_queue_id": customer_queue_id.id,
            "shopify_customer_data_id": customer_id or "",
            "name": name.strip(),
            "shopify_synced_customer_data": data,
            "shopify_instance_id": instance_id,
            "last_process_date": datetime.now(),
        }
        if not existing_customer_data:
            return synced_shopify_customers_line_obj.create(line_vals)
        return existing_customer_data.write({'shopify_synced_customer_data': data, 'state': 'draft'})

    @api.model
    def sync_shopify_customer_into_odoo(self):
        """
        This method is used to find customer queue which queue lines have state in draft and is_action_require is False.
        If cronjob has tried more than 3 times to process any queue then it marks that queue has need process to
        manually. It will be called from auto queue process cron.
        :author: Angel Patel @Emipro Technologies Pvt.Ltd on date 02/11/2019.
        :Task ID: 157065
        """
        shopify_customer_queue_obj = self.env["shopify.customer.data.queue.ept"]
        customer_queue_ids = []

        query = """select queue.id
            from shopify_customer_data_queue_line_ept as queue_line
            inner join shopify_customer_data_queue_ept as queue on queue_line.synced_customer_queue_id = queue.id
            where queue_line.state='draft' and queue.is_action_require = 'False'
            ORDER BY queue_line.create_date ASC"""
        self._cr.execute(query)
        customer_data_queue_list = self._cr.fetchall()
        if customer_data_queue_list:
            for customer_data_queue_id in customer_data_queue_list:
                if customer_data_queue_id[0] not in customer_queue_ids:
                    customer_queue_ids.append(customer_data_queue_id[0])
            queues = shopify_customer_queue_obj.browse(customer_queue_ids)
            self.filter_customer_queue_lines_and_post_message(queues)
        return True

    def filter_customer_queue_lines_and_post_message(self, queues):
        """
        This method is used to post a message if the queue is process more than 3 times otherwise
        it calls the child method to process the customer queue line.
        :param queues: Record of the customer queues.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 16 October 2020.
        @change: By Maulik Barad on 25-Nov-2020. Task : 167734 - Changes of cron execution utilisation.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        start = time.time()
        customer_queue_process_cron_time = queues.shopify_instance_id.get_shopify_cron_execution_time(
            "shopify_ept.process_shopify_customer_queue")

        for queue in queues:
            results = queue.synced_customer_queue_line_ids.filtered(lambda x: x.state == "draft")

            queue.queue_process_count += 1
            # queue.queue_process_count = 4
            if queue.queue_process_count > 3:
                queue.is_action_require = True
                note = _("<p>Need to process this customer queue manually.There are 3 attempts been made by " \
                         "automated action to process this queue,"
                         "<br/>- Ignore, if this queue is already processed.</p>")
                queue.message_post(body=note)
                if queue.shopify_instance_id.is_shopify_create_schedule:
                    common_log_line_obj.create_crash_queue_schedule_activity(queue, "shopify.customer.data.queue.ept",
                                                                             note)
                continue
            self._cr.commit()
            results.process_customer_queue_lines()
            if time.time() - start > customer_queue_process_cron_time - 60:
                return True

    def process_customer_queue_lines(self):
        """
        This method process the queue lines.
        """
        queues = self.synced_customer_queue_id

        for queue in queues:
            instance = queue.shopify_instance_id
            if instance.active:
                self.env.cr.execute("""update shopify_product_data_queue_ept set is_process_queue = False where
                is_process_queue = True""")
                self._cr.commit()

                self.customer_queue_commit_and_process(queue, instance)

                _logger.info("Customer Queue %s is processed.", queue.name)

        return True

    def customer_queue_commit_and_process(self, queue, instance):
        """ This method is used to commit the customer queue line after 10 customer queue line process
            and call the child method to process the customer queue line.
            :param queue: Record of customer queue.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17 October 2020 .
        """
        company_id = False
        shopify_partner_obj = self.env["shopify.res.partner.ept"]
        commit_count = 0
        for line in self:
            commit_count += 1
            if commit_count == 10:
                queue.is_process_queue = True
                self._cr.commit()
                commit_count = 0

            customer_data = json.loads(line.shopify_synced_customer_data)
            main_partner = shopify_partner_obj.shopify_create_contact_partner(customer_data, instance, line)
            if main_partner:
                for address in customer_data.get("addresses"):
                    if address.get("default"):
                        continue
                    shopify_partner_obj.shopify_create_or_update_address(instance, address, main_partner, "other")

                line.update(
                    {"state": "done", "last_process_date": datetime.now(), 'shopify_synced_customer_data': False})
            else:
                line.update({"state": "failed", "last_process_date": datetime.now()})
            queue.is_process_queue = False
