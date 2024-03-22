# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
import re
import logging
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api, _

from odoo.exceptions import UserError
from ..shopify.pyactiveresource.connection import ClientError
from .. import shopify

utc = pytz.utc

_logger = logging.getLogger("Shopify Order Queue")


class ShopifyOrderDataQueueEpt(models.Model):
    _name = "shopify.order.data.queue.ept"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Shopify Order Data Queue"

    name = fields.Char(help="Sequential name of imported order.", copy=False)
    shopify_instance_id = fields.Many2one('shopify.instance.ept', string='Instance',
                                          help="Order imported from this Shopify Instance.")
    state = fields.Selection([('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
                              ('completed', 'Completed'), ('failed', 'Failed')], tracking=True,
                             default='draft', copy=False, compute="_compute_queue_state",
                             store=True)
    shopify_order_common_log_lines_ids = fields.One2many("common.log.lines.ept", compute="_compute_log_lines")

    order_data_queue_line_ids = fields.One2many("shopify.order.data.queue.line.ept",
                                                "shopify_order_data_queue_id")
    order_queue_line_total_record = fields.Integer(string='Total Records',
                                                   compute='_compute_order_queue_line_record')
    order_queue_line_draft_record = fields.Integer(string='Draft Records',
                                                   compute='_compute_order_queue_line_record')
    order_queue_line_fail_record = fields.Integer(string='Fail Records',
                                                  compute='_compute_order_queue_line_record')
    order_queue_line_done_record = fields.Integer(string='Done Records',
                                                  compute='_compute_order_queue_line_record')

    order_queue_line_cancel_record = fields.Integer(string='Cancel Records',
                                                    compute='_compute_order_queue_line_record')
    created_by = fields.Selection([("import", "By Manually Import Process"), ("webhook", "By Webhook"),
                                   ("scheduled_action", "By Scheduled Action")],
                                  help="Identify the process that generated a queue.", default="import")
    is_process_queue = fields.Boolean('Is Processing Queue', default=False)
    running_status = fields.Char(default="Running...")
    queue_process_count = fields.Integer(string="Queue Process Times",
                                         help="it is used know queue how many time processed")
    is_action_require = fields.Boolean(default=False, help="it is used  to find the action require queue")
    queue_type = fields.Selection([("shipped", "Shipped Order Queue"), ("unshipped", "Unshipped Order Queue")],
                                  help="Identify to queue for which type of order import.")

    @api.depends('order_data_queue_line_ids.shopify_order_common_log_lines_ids')
    def _compute_log_lines(self):
        for line in self:
            line.shopify_order_common_log_lines_ids = line.order_data_queue_line_ids.shopify_order_common_log_lines_ids

    @api.depends('order_data_queue_line_ids.state')
    def _compute_queue_state(self):
        """
        Computes state from different states of queue lines.
        @author: Haresh Mori on Date 25-Dec-2019.
        """
        for record in self:
            if record.order_queue_line_total_record == record.order_queue_line_done_record + \
                    record.order_queue_line_cancel_record:
                record.state = "completed"
            elif record.order_queue_line_draft_record == record.order_queue_line_total_record:
                record.state = "draft"
            elif record.order_queue_line_total_record == record.order_queue_line_fail_record:
                record.state = "failed"
            else:
                record.state = "partially_completed"

    @api.depends('order_data_queue_line_ids.state')
    def _compute_order_queue_line_record(self):
        """This is used for the count of total records of order queue lines
            and display the count records in the form view order data queue.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2/11/2019.
        """
        for order_queue in self:
            queue_lines = order_queue.order_data_queue_line_ids
            order_queue.order_queue_line_total_record = len(queue_lines)
            order_queue.order_queue_line_draft_record = len(queue_lines.filtered(lambda x: x.state == "draft"))
            order_queue.order_queue_line_done_record = len(queue_lines.filtered(lambda x: x.state == "done"))
            order_queue.order_queue_line_fail_record = len(queue_lines.filtered(lambda x: x.state == "failed"))
            order_queue.order_queue_line_cancel_record = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.model_create_multi
    def create(self, vals):
        """This method used to create a sequence for Order Queue Data.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 04/11/2019.
        """
        for val in vals:
            sequence_id = self.env.ref('shopify_ept.seq_order_queue_data').ids
            if sequence_id:
                record_name = self.env['ir.sequence'].browse(sequence_id).next_by_id()
            else:
                record_name = '/'
            val.update({'name': record_name or ''})
        return super(ShopifyOrderDataQueueEpt, self).create(vals)

    def import_order_cron_action(self, ctx=False):
        """This method is used to import orders from the auto-import cron job.
        """
        if isinstance(ctx, dict):
            instance_id = ctx.get('shopify_instance_id')
            instance = self.env['shopify.instance.ept'].browse(instance_id)
            from_date = instance.last_date_order_import
            to_date = datetime.now()
            if not from_date:
                from_date = to_date - timedelta(3)

            self.shopify_create_order_data_queues(instance, from_date, to_date, created_by="scheduled_action")
        return True

    def import_shipped_order_cron_action(self, ctx=False):
        """This method is used to import orders from the auto-import cron job.
        """
        if not isinstance(ctx, dict):
            return True
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        from_date = instance.last_shipped_order_import_date
        to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(3)

        self.shopify_create_order_data_queues(instance, from_date, to_date, created_by="scheduled_action",
                                              order_type="shipped")
        return True

    def import_buy_with_prime_order_cron_action(self, ctx=False):
        """This method is used to import orders from the auto-import cron job.
        """
        if not isinstance(ctx, dict):
            return True
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        from_date = instance.last_buy_with_prime_order_import_date
        to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(3)

        self.shopify_create_order_data_queues(instance, from_date, to_date, created_by="scheduled_action",
                                              order_type="buy_with_prime")
        return True

    def convert_dates_by_timezone(self, instance, from_date, to_date):
        """
        This method converts the dates by timezone of the Shopify store to import orders.
        @param instance: Shopify Instance.
        @param from_date: From date for importing orders.
        @param to_date: To date for importing orders.
        @author: Maulik Barad on Date 28-Sep-2020.
        """
        if not instance.shopify_store_time_zone:
            shop_id = shopify.Shop.current()
            shop_detail = shop_id.to_dict()
            instance.write({'shopify_store_time_zone': shop_detail.get('iana_timezone')})
            self._cr.commit()

        from_date = pytz.utc.localize(from_date).astimezone(pytz.timezone(instance.shopify_store_time_zone or
                                                                          'UTC')).strftime('%Y-%m-%dT%H:%M:%S%z')
        to_date = pytz.utc.localize(to_date).astimezone(pytz.timezone(instance.shopify_store_time_zone or
                                                                      'UTC')).strftime('%Y-%m-%dT%H:%M:%S%z')
        return from_date, to_date

    def shopify_create_order_data_queues(self, instance, from_date, to_date, created_by="import",
                                         order_type="unshipped"):
        """
        This method used to create order data queues.
        @param : self, instance,  from_date, to_date, created_by, order_type
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 06/11/2019.
        Task Id : 157350
        @change: Maulik Barad on Date 10-Sep-2020.
        """
        order_data_queue_line_obj = self.env["shopify.order.data.queue.line.ept"]
        start = time.time()
        order_queues = []
        instance.connect_in_shopify()
        if order_type not in ["shipped", "buy_with_prime"]:
            queue_type = 'unshipped'
            for order_status_id in instance.shopify_order_status_ids:
                order_status = order_status_id.status
                order_ids = self.shopify_order_request(instance, from_date, to_date, order_status)

                if order_ids:
                    order_queues = order_data_queue_line_obj.create_order_data_queue_line(order_ids,
                                                                                          instance,
                                                                                          queue_type,
                                                                                          created_by)
                    if len(order_ids) >= 250:
                        order_queue_list = self.list_all_orders(order_ids, instance, created_by, queue_type)
                        order_queues += order_queue_list
                instance.last_date_order_import = to_date - timedelta(days=2)
        elif order_type == "shipped":
            order_queues = self.shopify_shipped_order_request(instance, from_date, to_date, created_by="import",
                                                              order_type="shipped")
            instance.last_shipped_order_import_date = to_date - timedelta(hours=1)
        else:
            if order_type == "buy_with_prime" and instance.import_buy_with_prime_shopify_order:
                order_queues = self.shopify_shipped_order_request(instance, from_date, to_date, created_by="import",
                                                                  order_type="buy_with_prime")
                instance.last_buy_with_prime_order_import_date = to_date - timedelta(days=2)
            else:
                _logger.info("Import Buy with Prime Configuration is not Active.")
        end = time.time()
        _logger.info("Imported Orders in %s seconds.", str(end - start))
        return order_queues

    def shopify_order_request(self, instance, from_date, to_date, order_type):
        """ This method used to pull the orders from shopify Store to Odoo.
            :param order_type: Which type of orders pull from Shopify to Odoo.
            Generally, they have two values 1) shipped 2) unshipped
            @return:order_ids
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17 October 2020 .
            Task_id:167537
        """
        from_date, to_date = self.convert_dates_by_timezone(instance, from_date, to_date)
        try:
            order_ids = shopify.Order().find(status="any",
                                             fulfillment_status=order_type,
                                             updated_at_min=from_date,
                                             updated_at_max=to_date, limit=250)
        except Exception as error:
            raise UserError(error)

        return order_ids

    def shopify_shipped_order_request(self, instance, from_date, to_date, order_type, created_by):
        """ This method is used to import shipped order from the shopify store to Odoo.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 30 December 2020 .
            Task_id:169381 - Gift card order import changes
        """
        order_data_queue_line_obj = self.env["shopify.order.data.queue.line.ept"]
        order_queues = []
        queue_type = 'shipped'
        order_ids = self.shopify_order_request(instance, from_date, to_date, queue_type)
        if order_ids and order_type == "buy_with_prime":
            order_ids = self.filter_buy_with_prime_order(instance, order_ids)
        if order_ids:
            order_queues = order_data_queue_line_obj.create_order_data_queue_line(order_ids,
                                                                                  instance,
                                                                                  queue_type,
                                                                                  created_by)
            if len(order_ids) >= 250:
                order_queue_list = self.list_all_orders(order_ids, instance, created_by, queue_type)
                order_queues += order_queue_list

        return order_queues

    def filter_buy_with_prime_order(self, instance, order_ids):
        buy_with_prime_order_ids = []
        for order_id in order_ids:
            order = order_id.to_dict()
            for buy_with_prime_tag in instance.buy_with_prime_tag_ids:
                if buy_with_prime_tag.name in order.get("tags"):
                    buy_with_prime_order_ids.append(order_id)
        return buy_with_prime_order_ids

    def list_all_orders(self, result, instance, created_by, queue_type):
        """
        This method used to get the list of orders from Shopify to Odoo.
        @param result: Response of order which received from Shopify store.
        @param order_type: Here we receive 2 type of order type(unshipped, shipped).
        @param created_by: To identify which process is created a queue record(webhook, Manually).
        @param instance:
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 06/11/2019.
        Task_id : 157350
        Modify on date 27/12/2019 Taken pagination changes
        @change : Maulik Barad on Date 10-Sep-2020.
        """
        order_data_queue_line_obj = self.env["shopify.order.data.queue.line.ept"]
        order_queue_list = []
        catch = ""

        while result:
            page_info = ""
            # link: link of next page.
            if not shopify.ShopifyResource.connection.response:
                link = result.metadata and result.metadata.get('headers', {}).get('Link', {})
            else:
                link = shopify.ShopifyResource.connection.response.headers.get(
                    "Link") if shopify.ShopifyResource.connection.response.headers.get(
                    "Link") else shopify.ShopifyResource.connection.response.headers.get("link")
            if not link or not isinstance(link, str):
                return order_queue_list

            for page_link in link.split(','):
                if page_link.find('next') > 0:
                    page_info = page_link.split(';')[0].strip('<>').split('page_info=')[1]
                    try:
                        result = shopify.Order().find(limit=250, page_info=page_info)
                    except ClientError as error:
                        if hasattr(error,
                                   "response") and error.response.code == 429 and error.response.msg == "Too Many Requests":
                            time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                            result = shopify.Order().find(limit=250, page_info=page_info)
                    except Exception as error:
                        raise UserError(error)
                    if result:
                        order_queues = order_data_queue_line_obj.create_order_data_queue_line(result, instance,
                                                                                              queue_type,
                                                                                              created_by)
                        order_queue_list += order_queues
            if catch == page_info:
                break
        return order_queue_list

    def import_order_process_by_remote_ids(self, instance, order_ids):
        """
        This method is used for get a order from shopify based on order ids and create its queue and process it.
        :param instance: Browsable object of shopify instance.
        :param order_ids: It contain the comma separated ids of shopify orders and its type is String.
        """
        order_data_queue_line_obj = self.env["shopify.order.data.queue.line.ept"]
        order_queue_obj = self.env["shopify.order.data.queue.ept"]
        queue_type = 'unshipped'
        if order_ids:
            instance.connect_in_shopify()
            # Below one line is used to find only character values from order ids.
            re.findall("[a-zA-Z]+", order_ids)
            if len(order_ids.split(',')) <= 50:
                # order_ids_list is a list of all order ids which response did not given by shopify.
                order_ids_list = list(set(re.findall(re.compile(r"(\d+)"), order_ids)))
                results = shopify.Order().find(ids=','.join(order_ids_list), status='any')
                if results:
                    _logger.info('%s Shopify order(s) imported from instance : %s', len(results), instance.name)
                    order_ids_list = [order_id.strip() for order_id in order_ids_list]
                    # Below process to identify which id response did not give by Shopify.
                    [order_ids_list.remove(str(result.id)) for result in results if str(result.id) in order_ids_list]
            else:
                raise UserError(_('Please enter the Order ids 50 or less'))
            if results:
                if order_ids_list:
                    _logger.warning("Orders are not found for ids :%s", str(order_ids_list))
                order_queues = order_data_queue_line_obj.create_order_data_queue_line(results,
                                                                                      instance,
                                                                                      queue_type,
                                                                                      created_by="import")
                return order_queues
                # order_queue_obj.browse(order_queues).order_data_queue_line_ids.process_import_order_queue_data()
        return True

    def create_schedule_activity(self, queue_id):
        """
        Author : Bhavesh Jadav 28/11/2019 this method use for create schedule activity on order data queue based on
        queue line.
        :model: model use for the model
        :return: True or False
        """
        mail_activity_obj = self.env['mail.activity']
        ir_model_obj = self.env['ir.model']
        model_id = ir_model_obj.search([('model', '=', 'shopify.order.data.queue.ept')])
        activity_type_id = queue_id and queue_id.shopify_instance_id.shopify_activity_type_id.id
        date_deadline = datetime.strftime(
            datetime.now() + timedelta(days=int(queue_id.shopify_instance_id.shopify_date_deadline)), "%Y-%m-%d")
        if queue_id:
            shopify_order_id_list = queue_id.order_data_queue_line_ids.filtered(
                lambda line: line.state == 'failed').mapped('shopify_order_id')
            if len(shopify_order_id_list) > 0:
                note = 'Your order has not been imported for Shopify Order Reference : %s' % str(
                    shopify_order_id_list)[1:-1]
                for user_id in queue_id.shopify_instance_id.shopify_user_ids:
                    mail_activity = mail_activity_obj.search([('res_model_id', '=', model_id.id),
                                                              ('user_id', '=', user_id.id),
                                                              ('res_name', '=', queue_id.name),
                                                              ('activity_type_id', '=', activity_type_id)])
                    note_2 = "<p>" + note + '</p>'
                    duplicate_activity = mail_activity.filtered(lambda x: x.note == note_2)
                    if not mail_activity or not duplicate_activity:
                        vals = {'activity_type_id': activity_type_id, 'note': note,
                                'res_id': queue_id.id, 'user_id': user_id.id or self._uid,
                                'res_model_id': model_id.id, 'date_deadline': date_deadline}
                        try:
                            mail_activity_obj.create(vals)
                        except Exception as error:
                            _logger.info("Unable to create schedule activity, Please give proper "
                                         "access right of this user :%s  ", user_id.name)
                            _logger.info(error)
        return True

    @api.model
    def retrieve_dashboard(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        dashboard = self.env['queue.line.dashboard']
        return dashboard.get_data(table='shopify.order.data.queue.line.ept')
