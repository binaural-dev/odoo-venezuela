# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class CommonLogLineEpt(models.Model):
    _inherit = "common.log.lines.ept"

    @api.model
    def update_module(self):
        shopify_instances = self.env['shopify.instance.ept'].search([])
        log_lines = self.env['common.log.lines.ept'].search([('shopify_instance_id', 'in', shopify_instances.ids)])
        for log_line in log_lines:
            if not log_line.module:
                log_line.write({'module': 'shopify_ept'})

    shopify_product_data_queue_line_id = fields.Many2one("shopify.product.data.queue.line.ept",
                                                         "Shopify Product Queue Line")
    shopify_order_data_queue_line_id = fields.Many2one("shopify.order.data.queue.line.ept",
                                                       "Shopify Order Queue Line")
    shopify_customer_data_queue_line_id = fields.Many2one("shopify.customer.data.queue.line.ept",
                                                          "Shopify Customer Queue Line")
    shopify_payout_report_line_id = fields.Many2one("shopify.payout.report.ept")
    shopify_export_stock_queue_line_id = fields.Many2one("shopify.export.stock.queue.line.ept",
                                                         "Shopify Export Stock Queue Line")
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Shopify Instance")

    def create_payout_schedule_activity(self, note, payout):
        """
        Using this method Notify to user through the log and schedule activity.
        @author: Maulik Barad on Date 10-Dec-2020.
        """
        if self:
            mail_activity_obj = self.env['mail.activity']

            activity_type_id = payout.instance_id.shopify_activity_type_id.id
            date_deadline = datetime.strftime(
                datetime.now() + timedelta(days=int(payout.instance_id.shopify_date_deadline)), "%Y-%m-%d")
            model_id = self.get_model_id("shopify.payout.report.ept")
            # group_accountant = self.env.ref('account.group_account_user')
            user_ids = payout.instance_id.shopify_payout_user_ids

            if note:
                for user_id in user_ids:
                    mail_activity = mail_activity_obj.search(
                        [('res_model_id', '=', model_id), ('user_id', '=', user_id.id), ('note', '=', note),
                         ('activity_type_id', '=', activity_type_id)])
                    if mail_activity:
                        continue
                    vals = {'activity_type_id': activity_type_id,
                            'note': note,
                            'res_id': payout.id,
                            'user_id': user_id.id or self._uid,
                            'res_model_id': model_id,
                            'date_deadline': date_deadline}
                    mail_activity_obj.create(vals)

    def create_crash_queue_schedule_activity(self, queue_id, model, note):
        """
        This method is used to create a schedule activity for the queue crash.
        Base on the Shopify configuration when any queue crash will create a schedule activity.
        :param queue_id: Record of the queue(customer,product and order)
        :param model_id: Record of model(customer,product and order)
        :param note: Message
        @author: Nilesh Parmar
        @author: Maulik Barad as created common method for all queues on dated 17-Feb-2020.
        Date: 07 February 2020.
        Task Id : 160579
        """
        mail_activity_obj = self.env['mail.activity']
        activity_type_id = queue_id and queue_id.shopify_instance_id.shopify_activity_type_id.id
        date_deadline = datetime.strftime(
            datetime.now() + timedelta(days=int(queue_id.shopify_instance_id.shopify_date_deadline)), "%Y-%m-%d")

        if queue_id:
            for user_id in queue_id.shopify_instance_id.shopify_user_ids:
                model_id = self._get_model_id(model).id
                mail_activity = mail_activity_obj.search(
                    [('res_model_id', '=', model_id), ('user_id', '=', user_id.id), ('res_id', '=', queue_id.id),
                     ('activity_type_id', '=', activity_type_id)])
                if not mail_activity:
                    vals = self.prepare_vals_for_schedule_activity(activity_type_id, note, queue_id, user_id, model_id,
                                                                   date_deadline)
                    try:
                        mail_activity_obj.create(vals)
                    except Exception as error:
                        _logger.info("Unable to create schedule activity, Please give proper "
                                     "access right of this user :%s  ", user_id.name)
                        _logger.info(error)
        return True

    def prepare_vals_for_schedule_activity(self, activity_type_id, note, queue_id, user_id, model_id, date_deadline):
        """ This method used to prepare a vals for the schedule activity.
            :param activity_type_id: Record of the activity type(email,call,meeting, to do)
            :param user_id: Record of user(whom to assign schedule activity)
            :param date_deadline: date of schedule activity dead line.
            @return: values
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 14 October 2020 .
            Task_id: 167537
        """
        values = {'activity_type_id': activity_type_id,
                  'note': note,
                  'res_id': queue_id.id,
                  'user_id': user_id.id or self._uid,
                  'res_model_id': model_id,
                  'date_deadline': date_deadline
                  }
        return values

    def create_common_log_line_ept(self, **kwargs):
        """
        Inherit This method for search any existing same log line placed or not
        @author: Nilam Kubavat @Emipro Technologies Pvt. Ltd on date 18 October 2022.
        """
        record_id = self.search_existing_record(**kwargs)
        if record_id:
            record_id.unlink()
        return super(CommonLogLineEpt, self).create_common_log_line_ept(**kwargs)

    def search_existing_record(self, **kwargs):
        # model = self._get_model_id(kwargs.get('model_name')).id
        model = self.env['ir.model'].sudo().search([('model', '=', kwargs.get('model_name'))]).id
        record_id = self.search([('shopify_instance_id', '=', kwargs.get('shopify_instance_id')),
                                 ('model_id', '=', model),
                                 ('message', '=', kwargs.get('message')),
                                 ('shopify_product_data_queue_line_id', '=',
                                  kwargs.get('shopify_product_data_queue_line_id')),
                                 ('shopify_order_data_queue_line_id', '=',
                                  kwargs.get('shopify_order_data_queue_line_id')),
                                 ('shopify_customer_data_queue_line_id', '=',
                                  kwargs.get('shopify_customer_data_queue_line_id')),
                                 ('shopify_payout_report_line_id', '=',
                                  kwargs.get('shopify_payout_report_line_id')),
                                 ('shopify_export_stock_queue_line_id', '=',
                                  kwargs.get('shopify_export_stock_queue_line_id'))
                                 ])
        return record_id
