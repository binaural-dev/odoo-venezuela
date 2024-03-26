# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import json
import logging
import time

from odoo import models, fields
from .. import shopify

_logger = logging.getLogger("Shopify Product Queue Line")


class ShopifyProductDataQueueLineEpt(models.Model):
    _name = "shopify.product.data.queue.line.ept"
    _description = "Shopify Product Data Queue Line"

    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    last_process_date = fields.Datetime()
    synced_product_data = fields.Text()
    product_data_id = fields.Char()
    state = fields.Selection([("draft", "Draft"), ("failed", "Failed"), ("done", "Done"),
                              ("cancel", "Cancelled")],
                             default="draft")
    product_data_queue_id = fields.Many2one("shopify.product.data.queue.ept", required=True,
                                            ondelete="cascade", copy=False)
    common_log_lines_ids = fields.One2many("common.log.lines.ept",
                                           "shopify_product_data_queue_line_id",
                                           help="Log lines created against which line.")
    name = fields.Char(string="Product", help="It contain the name of product")
    shopify_image_import_state = fields.Selection([('pending', 'Pending'), ('done', 'Done')], default='done',
                                                  help="It used to identify that product image imported explicitly")

    def auto_import_product_queue_line_data(self):
        """
        This method is used to find product queue which queue lines have state in draft and is_action_require is False.
        If cronjob has tried more than 3 times to process any queue then it marks that queue has need process to
        manually. It will be called from auto queue process cron.
        @author: Maulik Barad on Date 31-Aug-2020.
        """
        product_data_queue_ids = []
        product_data_queue_obj = self.env["shopify.product.data.queue.ept"]

        query = """select queue.id
                from shopify_product_data_queue_line_ept as queue_line
                inner join shopify_product_data_queue_ept as queue on queue_line.product_data_queue_id = queue.id
                where queue_line.state='draft' and queue.is_action_require = 'False'
                ORDER BY queue_line.create_date ASC"""
        self._cr.execute(query)
        product_data_queue_list = self._cr.fetchall()
        if product_data_queue_list:
            for result in product_data_queue_list:
                if result[0] not in product_data_queue_ids:
                    product_data_queue_ids.append(result[0])

            queues = product_data_queue_obj.browse(product_data_queue_ids)
            self.process_product_queue_and_post_message(queues)
        return

    def process_product_queue_and_post_message(self, queues):
        """
        This method is used to post a message if the queue is process more than 3 times otherwise
        it calls the child method to process the product queue line.
        :param queues: Records of product queue.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
        Task_id: 167537
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        start = time.time()
        product_queue_process_cron_time = queues.shopify_instance_id.get_shopify_cron_execution_time(
            "shopify_ept.process_shopify_product_queue")

        for queue in queues:
            product_data_queue_line_ids = queue.product_data_queue_lines

            # For counting the queue crashes and creating schedule activity for the queue.
            queue.queue_process_count += 1
            #queue.queue_process_count = 4
            if queue.queue_process_count > 3:
                queue.is_action_require = True
                note = "<p>Need to process this product queue manually.There are 3 attempts been made by " \
                       "automated action to process this queue,<br/>- Ignore, if this queue is already processed.</p>"
                queue.message_post(body=note)
                if queue.shopify_instance_id.is_shopify_create_schedule:
                    common_log_line_obj.create_crash_queue_schedule_activity(queue, "shopify.product.data.queue.ept",
                                                                             note)
                return True

            self._cr.commit()
            product_data_queue_line_ids.process_product_queue_line_data()
            if time.time() - start > product_queue_process_cron_time - 60:
                return True
        return True

    def process_product_queue_line_data(self):
        """
        This method is used to processes product queue lines.
        @author: Maulik Barad on Date 31-Aug-2020.
        """
        shopify_product_template_obj = self.env["shopify.product.template.ept"]

        queue_id = self.product_data_queue_id if len(self.product_data_queue_id) == 1 else False

        if queue_id:
            shopify_instance = queue_id.shopify_instance_id
            if shopify_instance.active:
                _logger.info("Instance %s is not active.", shopify_instance.name)

                self.env.cr.execute(
                    """update shopify_product_data_queue_ept set is_process_queue = False where is_process_queue = True""")
                self._cr.commit()
                for product_queue_line in self:
                    shopify_product_template_obj.shopify_sync_products(product_queue_line,
                                                                       False,
                                                                       shopify_instance)
                    queue_id.is_process_queue = True
                    self._cr.commit()
        return True

    def replace_product_response(self):
        """
        This method used to replace the product data response in the failed queue line. It will
        call from the product queue line button.
        @author: Haresh Mori @Emipro Technologies Pvt.Ltd on date 21/1/2020.
        """
        instance = self.shopify_instance_id
        if instance.active:
            _logger.info("Instance %s is not active.", instance.name)
            instance.connect_in_shopify()
            if self.product_data_id:
                result = shopify.Product().find(self.product_data_id)
                result = result.to_dict()
                data = json.dumps(result)
                self.write({"synced_product_data": data, "state": "draft"})
                self._cr.commit()
                self.process_product_queue_line_data()
        return True

    def shopify_image_import(self):
        """ This method is used to import the product images explicitly.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 7 December 2020 .
            Task_id: 167684 - Changes for image import explicitly
        """
        shopify_template_obj = self.env['shopify.product.template.ept']
        instance_obj = self.env['shopify.instance.ept']
        start_time = time.time()
        image_import_cron_time = instance_obj.get_shopify_cron_execution_time(
            "shopify_ept.shopify_ir_cron_import_image_explicitly")
        product_queue_lines = self.query_find_queue_line_for_import_image()
        for queue in product_queue_lines:
            product_queue = self.browse(queue)
            template_data = product_queue.synced_product_data
            template_data = json.loads(template_data)
            shopify_template = shopify_template_obj.search([('shopify_tmpl_id', '=', product_queue.product_data_id),
                                                            ('shopify_instance_id', '=',
                                                             product_queue.shopify_instance_id.id)], limit=1)
            if not shopify_template:
                continue
            shopify_template.shopify_sync_product_images(template_data)
            product_queue.write({'shopify_image_import_state': 'done', "synced_product_data": False})
            self._cr.commit()
            if time.time() - start_time > image_import_cron_time - 60:
                return True

        return True

    def query_find_queue_line_for_import_image(self):
        """ This method is used to search product queue lines which are remaining to import an image for the product.
            @return: product_queue_list
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 7 December 2020 .
            Task_id: 167684 - Changes for image import explicitly.
        """
        query = """select id from shopify_product_data_queue_line_ept
                    where state='done' and shopify_image_import_state = 'pending'
                    ORDER BY create_date ASC"""
        self._cr.execute(query)
        product_queue_lines = self._cr.fetchall()
        return product_queue_lines
