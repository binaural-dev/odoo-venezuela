import logging
import pytz
from odoo import models, fields, api

utc = pytz.utc

_logger = logging.getLogger("Shopify Export Stock Queue")


class ShopifyExportStockQueueEpt(models.Model):
    _name = "shopify.export.stock.queue.ept"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Shopify Export Stock Queue"

    name = fields.Char(size=120)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")], default="draft",
                             compute="_compute_queue_state", store=True, tracking=True)
    export_stock_queue_line_ids = fields.One2many("shopify.export.stock.queue.line.ept",
                                                  "export_stock_queue_id",
                                                  string="Export Stock Queue Lines")
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

    @api.depends('export_stock_queue_line_ids.common_log_lines_ids')
    def _compute_log_lines(self):
        for line in self:
            line.common_log_lines_ids = line.export_stock_queue_line_ids.common_log_lines_ids

    @api.depends("export_stock_queue_line_ids.state")
    def _compute_queue_line_record(self):
        """This is used for count of total record of export_stock queue line base on it's state and
        it display in the form view of export stock queue.
        @author: Nilam Kubavat @Emipro Technologies Pvt.Ltd on date 31-Aug-2022.
        Task Id : 199065
        """
        for export_stock_queue in self:
            queue_lines = export_stock_queue.export_stock_queue_line_ids
            export_stock_queue.queue_line_total_records = len(queue_lines)
            export_stock_queue.queue_line_draft_records = len(queue_lines.filtered(lambda x: x.state == "draft"))
            export_stock_queue.queue_line_fail_records = len(queue_lines.filtered(lambda x: x.state == "failed"))
            export_stock_queue.queue_line_done_records = len(queue_lines.filtered(lambda x: x.state == "done"))
            export_stock_queue.queue_line_cancel_records = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.depends("export_stock_queue_line_ids.state")
    def _compute_queue_state(self):
        """
        Computes queue state from different states of queue lines.
        @author: Nilam Kubavat @Emipro Technologies Pvt.Ltd on date 31-Aug-2022.
        Task Id : 199065
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
        """This method used to create a sequence for export_stock queue.
            @author: Nilam Kubavat @Emipro Technologies Pvt.Ltd on date 31-Aug-2022.
        Task Id : 199065
        """
        for val in vals:
            sequence_id = self.env.ref("shopify_ept.seq_export_stock_queue").ids
            if sequence_id:
                record_name = self.env["ir.sequence"].browse(sequence_id).next_by_id()
            else:
                record_name = "/"
            val.update({"name": record_name or ""})
        return super(ShopifyExportStockQueueEpt, self).create(vals)

    def create_export_stock_queue(self, instance, export_stock_data):
        """
        Creates export stock queues and adds queue lines in it.
        @author: Nilam Kubavat @Emipro Technologies Pvt.Ltd on date 31-Aug-2022.
        Task Id : 199065
        """
        export_stock_queue = self
        count = 50
        for data in export_stock_data:
            if count == 50:
                count = 0
                export_stock_queue = self.shopify_create_export_stock_queue(instance)
                message = "Export Stock Queue Created %s" % ', '.join(export_stock_queue.mapped('name'))
                if self.env.context.get('queue_created_by'):
                    self.env["bus.bus"]._sendone(self.env.user.partner_id, 'simple_notification',
                                                 {"title": "Shopify Connector",
                                                  "message": message, "sticky": False, "warning": True})
                self._cr.commit()
                _logger.info(message)
            self.shopify_create_export_stock_queue_line(data, instance, export_stock_queue)
            count += 1

        return export_stock_queue

    def shopify_create_export_stock_queue(self, instance):
        """
        This method used to create a export stock queue.
         @author: Nilam Kubavat @Emipro Technologies Pvt.Ltd on date 31-Aug-2022.
        Task Id : 199065
        """
        product_queue_vals = {
            "shopify_instance_id": instance and instance.id or False
        }
        return self.create(product_queue_vals)

    def shopify_create_export_stock_queue_line(self, data, instance, export_stock_queue):
        """
        This method used to create a export stock data queue line.
        @author: Nilam Kubavat @Emipro Technologies Pvt.Ltd on date 31-Aug-2022.
        Task Id : 199065
        """
        exists_export_stock_queue_line = self.env["shopify.export.stock.queue.line.ept"].search(
            [('shopify_product_id', '=', data.get("shopify_product_id").id),
             ("location_id", "=", data.get('location_id')),
             ("shopify_instance_id", '=', instance.id),
             ("inventory_item_id", "=", data.get('inventory_item_id')),
             ("state", "=", "draft")])
        if not exists_export_stock_queue_line:
            export_stock_queue_line_vals = {
                "shopify_instance_id": instance and instance.id or False,
                'name': data.get("shopify_product_id").default_code,
                "inventory_item_id": data.get('inventory_item_id'),
                "shopify_product_id": data.get("shopify_product_id").id,
                'location_id': data.get('location_id'),
                'quantity': int(data.get('quantity')),
                "export_stock_queue_id": export_stock_queue and export_stock_queue.id or False
            }
            self.env['shopify.export.stock.queue.line.ept'].create(export_stock_queue_line_vals)
        else:
            exists_export_stock_queue_line.write({'quantity': int(data.get('quantity'))})
        return True

    @api.model
    def retrieve_dashboard(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        dashboard = self.env['queue.line.dashboard']
        return dashboard.get_data(table='shopify.export.stock.queue.line.ept')
