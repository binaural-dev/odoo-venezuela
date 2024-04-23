# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
import json
import logging
import re
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

_logger = logging.getLogger("Shopify Product Queue")


class ShopifyProductDataQueue(models.Model):
    _name = "shopify.product.data.queue.ept"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Shopify Product Data Queue"

    name = fields.Char(size=120)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")], default="draft",
                             compute="_compute_queue_state", store=True, tracking=True)
    product_data_queue_lines = fields.One2many("shopify.product.data.queue.line.ept",
                                               "product_data_queue_id",
                                               string="Product Queue Lines")
    common_log_lines_ids = fields.One2many("common.log.lines.ept", compute="_compute_log_lines")
    queue_line_total_records = fields.Integer(string="Total Records",
                                              compute="_compute_queue_line_record")
    queue_line_draft_records = fields.Integer(string="Draft Records",
                                              compute="_compute_queue_line_record")
    queue_line_fail_records = fields.Integer(string="Fail Records",
                                             compute="_compute_queue_line_record")
    queue_line_done_records = fields.Integer(string="Done Records",
                                             compute="_compute_queue_line_record")
    queue_line_cancel_records = fields.Integer(string="Cancelled Records",
                                               compute="_compute_queue_line_record")
    created_by = fields.Selection([("import", "By Import Process"), ("webhook", "By Webhook")],
                                  help="Identify the process that generated a queue.",
                                  default="import")
    is_process_queue = fields.Boolean("Is Processing Queue", default=False)
    running_status = fields.Char(default="Running...")
    is_action_require = fields.Boolean(default=False)
    queue_process_count = fields.Integer(string="Queue Process Times",
                                         help="it is used know queue how many time processed")
    skip_existing_product = fields.Boolean(string="Do Not Update Existing Products")

    @api.depends('product_data_queue_lines.common_log_lines_ids')
    def _compute_log_lines(self):
        for line in self:
            line.common_log_lines_ids = line.product_data_queue_lines.common_log_lines_ids

    @api.depends("product_data_queue_lines.state")
    def _compute_queue_line_record(self):
        """This is used for count of total record of product queue line base on it's state and
            it display in the form view of product queue.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2/11/2019.
        """
        for product_queue in self:
            queue_lines = product_queue.product_data_queue_lines
            product_queue.queue_line_total_records = len(queue_lines)
            product_queue.queue_line_draft_records = len(queue_lines.filtered(lambda x: x.state == "draft"))
            product_queue.queue_line_fail_records = len(queue_lines.filtered(lambda x: x.state == "failed"))
            product_queue.queue_line_done_records = len(queue_lines.filtered(lambda x: x.state == "done"))
            product_queue.queue_line_cancel_records = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.depends("product_data_queue_lines.state")
    def _compute_queue_state(self):
        """
        Computes queue state from different states of queue lines.
        @author: Haresh Mori on Date 25-Dec-2019.
        """
        for record in self:
            if record.queue_line_total_records == record.queue_line_done_records + record.queue_line_cancel_records:
                record.state = "completed"
            elif record.queue_line_draft_records == record.queue_line_total_records:
                record.state = "draft"
            elif record.queue_line_total_records == record.queue_line_fail_records:
                record.state = "failed"
            else:
                record.state = "partially_completed"

    @api.model_create_multi
    def create(self, vals):
        """This method used to create a sequence for product queue.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 05/10/2019.
        """
        for val in vals:
            sequence_id = self.env.ref("shopify_ept.seq_product_queue_data").ids
            if sequence_id:
                record_name = self.env["ir.sequence"].browse(sequence_id).next_by_id()
            else:
                record_name = "/"
            val.update({"name": record_name or ""})
        return super(ShopifyProductDataQueue, self).create(vals)

    def create_product_queues(self, instance, results, skip_existing_product, template_ids=""):
        """
        Creates product queues and adds queue lines in it.
        @param instance: Shopify Instance.
        @param results: Response of Products from shopify.
        @param template_ids: List of ids of templates.
        @return: List of Product queues.
        @author: Maulik Barad on Date 28-Aug-2020.
        """
        product_queue_list = []
        order_data_queue_line = self.env['shopify.order.data.queue.line.ept']
        count = 125
        product_queue = False
        for result in results:
            if count == 125:
                product_queue = self.shopify_create_product_queue(instance, skip_existing_product=skip_existing_product)
                message = "Product Queue Created %s" % ', '.join(product_queue.mapped('name'))
                if self.env.context.get('queue_created_by'):
                    order_data_queue_line.generate_simple_notification(message)
                self._cr.commit()
                _logger.info(message)
                count = 0
                if template_ids:
                    product_queue.message_post(body=_('%s products are not imported') % ','.join(template_ids))
            self.shopify_create_product_data_queue_line(result, instance, product_queue)
            count = count + 1
        if product_queue and not product_queue.product_data_queue_lines:
            product_queue.unlink()
        elif product_queue:
            product_queue_list.append(product_queue.id)
        self._cr.commit()
        return product_queue_list

    def shopify_create_product_data_queue(self, instance, import_based_on='', from_date=False,
                                          to_date=False, skip_existing_product=False,
                                          template_ids="",is_import_draft_product=False):
        """
        This method used to create a product data queue while syncing product from Shopify to Odoo.
        @param instance: Shopify Instance.
        @param import_based_on: When import all products, by which date products should be imported. Date 01-Jun-2021.
        @param from_date: From date. Date 01-Jun-2021.
        @param to_date: To date. Date 01-Jun-2021.
        @param skip_existing_product: skip_existing_product False then it will update product values existing sync
        product, if True then it will not update product values in existing products.
        @param template_ids: Ids of shopify template.
        @author: Maulik Barad on Date 28-Aug-2020.
        @return: List of Product queues.
        """
        instance.connect_in_shopify()
        product_queue_list = []
        results = False
        if template_ids:
            product_queue_list += self.import_products_by_remote_ids(template_ids, instance)
            if product_queue_list:
                results = True
        else:
            results = self.find_shopify_draft_prodcut_for_import('active', import_based_on, from_date, to_date)
            product_queue_list += self.create_product_queues(instance, results, skip_existing_product)

            if len(results) >= 250:
                product_queue_list += self.shopify_list_all_products(instance, results, skip_existing_product)
            if results:
                instance.shopify_last_date_product_import = datetime.now()

            if is_import_draft_product:
                results = self.find_shopify_draft_prodcut_for_import('draft', import_based_on, from_date, to_date)
                product_queue_list += self.create_product_queues(instance, results, skip_existing_product)

                if len(results) >= 250:
                    product_queue_list += self.shopify_list_all_products(instance, results, skip_existing_product)
        if not results:
            _logger.info("No Products found to be imported from Shopify.")
            return False

        return product_queue_list

    def find_shopify_draft_prodcut_for_import(self, product_status, import_based_on, from_date, to_date):
        """
        This method used to find product in shopify store which is in draft state.
        @author: Yagnik Joshi on Date 29-November-2020.
        """
        if import_based_on == "create_date":
            results = shopify.Product().find(status=product_status, created_at_min=from_date, created_at_max=to_date,
                                             limit=250)
        else:
            results = shopify.Product().find(status=product_status, updated_at_min=from_date, updated_at_max=to_date,
                                             limit=250)
        return results

    def import_products_by_remote_ids(self, template_ids, instance):
        """ This method is used to import Shopify products into Odoo using remote ids(open product in Shopify store,
            in URL you can find remote-id,ex:https://new-emipro.myshopify.com/admin/products/4333282951223,
            here is remote id: 4333282951223).
            :param template_ids: Remote ids of Shopify template.
            @return: product_queue_list
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
            Task_id: 167537
        """
        # Below one line is used to find only character values from template ids.
        product_queue_list = []
        re.findall("[a-zA-Z]+", template_ids)
        if len(template_ids.split(",")) <= 100:
            # The template_ids is a list of all template ids which response did not given by
            # shopify.
            template_ids = list(set(re.findall(re.compile(r"(\d+)"), template_ids)))
            results = shopify.Product().find(ids=",".join(template_ids))
            if results:
                _logger.info(
                    "Length of Shopify Products %s import from instance : %s", len(results), instance.name)
                template_ids = [template_id.strip() for template_id in template_ids]
                # Below process to identify which id response did not give by Shopify.
                [template_ids.remove(str(result.id)) for result in results if str(result.id) in template_ids]
                product_queue_list += self.create_product_queues(instance, results, False, template_ids)
        else:
            raise UserError(_("Please enter the product template ids 100 or less"))
        return product_queue_list

    def shopify_list_all_products(self, instance, result, skip_existing_product):
        """This method used to call the page wise data of product to import from Shopify to Odoo.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 14/10/2019.
            Modify on date 27/12/2019 Taken pagination changes.
        """
        product_queue_list = []
        catch = ""
        while result:
            page_info = ""
            link = shopify.ShopifyResource.connection.response.headers.get(
                "Link") if shopify.ShopifyResource.connection.response.headers.get(
                "Link") else shopify.ShopifyResource.connection.response.headers.get("link")
            if not link or not isinstance(link, str):
                return product_queue_list
            for page_link in link.split(","):
                if page_link.find("next") > 0:
                    page_info = page_link.split(";")[0].strip("<>").split("page_info=")[1]
                    try:
                        result = shopify.Product().find(page_info=page_info, limit=250)
                    except ClientError as error:
                        if hasattr(error,
                                   "response") and error.response.code == 429 and error.response.msg == "Too Many Requests":
                            time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                            result = shopify.Product().find(page_info=page_info, limit=250)
                    except Exception as error:
                        raise UserError(error)
                    if result:
                        product_queue_list += self.create_product_queues(instance, result, skip_existing_product)
            if catch == page_info:
                break
        return product_queue_list

    def shopify_create_product_queue(self, instance, created_by="import", skip_existing_product=False):
        """
        This method used to create a product queue.
        @param instance: Shopify Instance.
        @param created_by: By which process, we are creating the queue.
        @author: Maulik Barad on Date 28-Aug-2020.
        """
        product_queue_vals = {
            "shopify_instance_id": instance and instance.id or False,
            "created_by": created_by,
            "skip_existing_product": skip_existing_product
        }
        return self.create(product_queue_vals)

    def shopify_create_product_data_queue_line(self, result, instance, product_data_queue):
        """
        This method used to create a product data queue line.
        @param result: Response of a product from shopify.
        @param instance: Shopify Instance.
        @param product_data_queue: Product data queue to attach the queue line with.
        @author: Maulik Barad on Date 01-Sep-2020.
        """
        product_data_queue_line_obj = self.env["shopify.product.data.queue.line.ept"]

        # No need to convert the response into dictionary, when response is coming from webhook.
        if not isinstance(result, dict):
            result = result.to_dict()
        data = json.dumps(result)
        image_import_state = 'done'
        if instance.sync_product_with_images:
            image_import_state = 'pending'

        existing_product_data = product_data_queue_line_obj.search(
            [('product_data_id', '=', result.get('id')), ('shopify_instance_id', '=', instance.id),
             ('state', 'in', ['draft', 'failed']), ('product_data_queue_id.is_action_require', '=', False)])
        existing_product_queue = existing_product_data.product_data_queue_id
        product_queue_line_vals = {"product_data_id": result.get("id"),
                                   "shopify_instance_id": instance and instance.id or False,
                                   "name": result.get("title"),
                                   "synced_product_data": data,
                                   "product_data_queue_id": product_data_queue and product_data_queue.id or False,
                                   "shopify_image_import_state": image_import_state,
                                   }
        if not existing_product_data:
            product_data_queue_line_obj.create(product_queue_line_vals)
        else:
            existing_product_data.write({"synced_product_data": data, 'state': 'draft'})
            if not existing_product_queue.product_data_queue_lines:
                existing_product_queue.unlink()
        return True

    def create_schedule_activity_for_product(self, queue_line, from_sale=False):
        """
        This method is used for create schedule activity will product has extra attribute
        :param queue_line: is use for order queue_line or product queue_line
        :param from_sale:is use for identify its from sale process or product process
        @author:Bhavesh Jadav 13/12/2019
        """
        mail_activity_obj = self.env['mail.activity']
        common_log_line_obj = self.env['common.log.lines.ept']
        queue_id, model_id, data_ref, note = self.assign_queue_model_date_ref_note(from_sale, queue_line)
        activity_type_id = queue_id and queue_id.shopify_instance_id.shopify_activity_type_id.id
        date_deadline = datetime.strftime(
            datetime.now() + timedelta(days=int(queue_id.shopify_instance_id.shopify_date_deadline)), "%Y-%m-%d")
        if queue_id:
            note_2 = "<p>" + note + '</p>'
            for user_id in queue_id.shopify_instance_id.shopify_user_ids:
                mail_activity = mail_activity_obj.search(
                    [('res_model_id', '=', model_id.id), ('user_id', '=', user_id.id),
                     ('res_name', '=', queue_id.name),
                     ('activity_type_id', '=', activity_type_id)])
                duplicate_note = mail_activity.filtered(lambda x: x.note == note_2)
                if not mail_activity or not duplicate_note:
                    vals = common_log_line_obj.prepare_vals_for_schedule_activity(activity_type_id, note, queue_id,
                                                                                  user_id, model_id.id, date_deadline)
                    try:
                        mail_activity_obj.create(vals)
                    except Exception as error:
                        _logger.info("Couldn't create schedule activity :%s", str(error))
        return True

    def assign_queue_model_date_ref_note(self, from_sale, queue_line):
        """ This method is assign queue, model, date ref, and note base on which process called this method.
            there is two possibility, it calls from sale order while product is not found in odoo
            and then the auto-create product is true and second from the product sync process.
            :param from_sale : It true while process call from sale order import.
            :param queue_line: Record of queue line(order queue line or product queue line)
            @return: queue_id, model_id, data_ref, note
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
            Task_id: 167537
        """
        ir_model_obj = self.env['ir.model']
        if from_sale:
            queue_id = queue_line.shopify_order_data_queue_id
            model_id = ir_model_obj.search([('model', '=', 'shopify.order.data.queue.ept')])
            data_ref = queue_line.shopify_order_id
            note = _('Your order has not been imported because of the product of order Has a new attribute Shopify ' \
                     'Order Reference : %s') % data_ref
        else:
            queue_id = queue_line.product_data_queue_id
            model_id = ir_model_obj.search([('model', '=', 'shopify.product.data.queue.ept')])
            data_ref = queue_line.product_data_id
            note = _('Your product was not synced because you tried to add new attribute | Product Data Reference ' \
                     ': %s') % data_ref

        return queue_id, model_id, data_ref, note

    def create_shopify_product_queue_from_webhook(self, product_data, instance):
        """
        This method used to create a product queue while receive a response from webhook.
        @author: Dipak Gogiya on Date 10-Jan-2020.
        """
        product_data_queue = self.search([("created_by", "=", "webhook"), ("state", "=", "draft"),
                                          ("shopify_instance_id", "=", instance.id), ('is_action_require', '=', False)])
        if product_data_queue:
            message = "Product %s added into Queue %s." % (product_data.get("id"), product_data_queue.name)
        else:
            product_data_queue = self.shopify_create_product_queue(instance, "webhook")
            message = "Product Queue %s created." % product_data_queue.name
        _logger.info(message)

        self.shopify_create_product_data_queue_line(product_data, instance, product_data_queue)

        if len(self.product_data_queue_lines) == 50:
            product_data_queue.product_data_queue_lines.process_product_queue_line_data()
            _logger.info("Processed product %s of %s via Webhook Successfully.", product_data.get("id"), instance.name)
        return True

    @api.model
    def retrieve_dashboard(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        dashboard = self.env['queue.line.dashboard']
        return dashboard.get_data(table='shopify.product.data.queue.line.ept', )

    def import_product_cron_action(self, ctx=False):
        """
        This method is used to import Products from the auto-import cron job.
        """
        if isinstance(ctx, dict):
            instance_id = ctx.get('shopify_instance_id')
            instance = self.env['shopify.instance.ept'].browse(instance_id)
            from_date = instance.shopify_last_date_product_import
            to_date = datetime.now()
            import_products_based_on_date = "update_date"
            skip_existing_product = False
            if not from_date:
                from_date = to_date - timedelta(30)
            self.shopify_create_product_data_queue(instance, import_products_based_on_date, from_date, to_date,
                                                   skip_existing_product)
        return True
