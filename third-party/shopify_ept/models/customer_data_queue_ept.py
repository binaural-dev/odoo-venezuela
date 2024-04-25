# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class ShopifyCustomerDataQueueEpt(models.Model):
    """ This model is used to handle the customer data queue."""
    _name = "shopify.customer.data.queue.ept"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Shopify Synced Customer Data"

    name = fields.Char(size=120, readonly=True)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")], compute="_compute_queue_state",
                             default="draft", store=True, tracking=True)
    synced_customer_queue_line_ids = fields.One2many("shopify.customer.data.queue.line.ept",
                                                     "synced_customer_queue_id", "Customers")
    total_record_count = fields.Integer(string="Total Records Count",
                                        compute="_compute_total_record_count")
    draft_state_count = fields.Integer(compute="_compute_total_record_count")
    fail_state_count = fields.Integer(compute="_compute_total_record_count")
    done_state_count = fields.Integer(compute="_compute_total_record_count")
    cancel_state_count = fields.Integer(compute="_compute_total_record_count")
    common_log_lines_ids = fields.One2many("common.log.lines.ept", compute="_compute_log_lines")
    record_created_from = fields.Selection([("webhook", "From Webhook"), ("import_process", "From Import Process")])
    is_process_queue = fields.Boolean("Is Processing Queue", default=False)
    running_status = fields.Char(default="Running...")
    is_action_require = fields.Boolean(default=False)
    queue_process_count = fields.Integer(help="It is used for know, how many time queue is processed.")

    @api.depends('synced_customer_queue_line_ids.common_log_lines_ids')
    def _compute_log_lines(self):
        for line in self:
            line.common_log_lines_ids = line.synced_customer_queue_line_ids.common_log_lines_ids

    @api.depends("synced_customer_queue_line_ids.state")
    def _compute_total_record_count(self):
        """
        This method used to count records of queue line base on the queue state.
        It displays the count records in the form view of the queue.
        :author: Angel Patel @Emipro Technologies Pvt.Ltd on date 02/11/2019.
        :Task ID: 157065
        """
        for record in self:
            queue_lines = record.synced_customer_queue_line_ids
            record.total_record_count = len(queue_lines)
            record.draft_state_count = len(queue_lines.filtered(lambda x: x.state == "draft"))
            record.done_state_count = len(queue_lines.filtered(lambda x: x.state == "done"))
            record.fail_state_count = len(queue_lines.filtered(lambda x: x.state == "failed"))
            record.cancel_state_count = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.depends("synced_customer_queue_line_ids.state")
    def _compute_queue_state(self):
        """
        This method is used to set the queue state base on the computes state from different states of queue lines.
        @author: Haresh Mori on Date 25-Dec-2019.
        """
        for record in self:
            if record.total_record_count == record.done_state_count + record.cancel_state_count:
                record.state = "completed"
            elif record.draft_state_count == record.total_record_count:
                record.state = "draft"
            elif record.total_record_count == record.fail_state_count:
                record.state = "failed"
            else:
                record.state = "partially_completed"

    @api.model_create_multi
    def create(self, vals):
        """
        This method used to create a sequence of customer queue.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 25/10/2019.
        :Task ID: 157065
        """
        for val in vals:
            seq = self.env["ir.sequence"].next_by_code("shopify.customer.data.queue.ept") or "/"
            val.update({"name": seq or ""})
        return super(ShopifyCustomerDataQueueEpt, self).create(vals)

    @api.model
    def create_customer_queue(self, instance, record_created_from):
        """
        This method used to create a customer queue.
        :param instance: Record of instance
        :param record_created_from: (webhook, import_process)It is used to identify which process created the
        queue record.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 08/1/2020.
        """
        customer_queue_vals = {
            "shopify_instance_id": instance and instance.id or False,
            "record_created_from": record_created_from
        }
        return self.create(customer_queue_vals)

    @api.model
    def retrieve_dashboard(self, *args, **kwargs):
        dashboard = self.env['queue.line.dashboard']
        return dashboard.get_data(table='shopify.customer.data.queue.line.ept')
