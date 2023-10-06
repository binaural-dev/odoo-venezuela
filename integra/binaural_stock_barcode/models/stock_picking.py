from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"
    _order = "create_date desc"

    picker_id = fields.Many2one(
        "hr.employee", string="Picker", domain=[("role_picking", "=", "picker")]
    )
    picking_time_ids = fields.One2many("stock.picking.time", "pick_id")
    cart_id = fields.Many2one("stock.picking.cart", string="Cart")

    supervisor_approve_to_edit_id = fields.Many2one("hr.employee", readonly=False)
    supervisor_approve_for_incomplete_qty_id = fields.Many2one("hr.employee", readonly=False)

    operation_start_date = fields.Datetime(compute="_compute_time_elapsed")
    operation_pause_date = fields.Datetime(compute="_compute_time_elapsed")
    operation_end_date = fields.Datetime(compute="_compute_time_elapsed")
    operation_state = fields.Selection(
        selection=[
            ("paused", "Pause"),
            ("ready", "To start"),
            ("in_process", "In process"),
            ("finished", "Finished"),
            ("cancel", "Cancel"),
        ],
        compute="_compute_operation_state",
        default="ready",
        store=True,
        copy=False,
    )
    total_time_elapsed = fields.Float(string="Total time elapsed", compute="_compute_time_elapsed")
    total_lines = fields.Integer(compute="_compute_total_lines")

    @api.depends("move_line_ids_without_package")
    def _compute_total_lines(self):
        for picking_report in self:
            picking_report.total_lines = len(
                [line for line in picking_report.mapped("move_line_ids_without_package")]
            )

    def set_supervisor_to_edit(self, supervisor_id):
        user_id = self.env["res.users"].sudo().browse(supervisor_id)
        self.supervisor_approve_to_edit_id = user_id.employee_id

    def set_supervisor_for_incomplete_qty(self, supervisor_id):
        user_id = self.env["res.users"].sudo().browse(supervisor_id)
        self.supervisor_approve_for_incomplete_qty_id = user_id.employee_id

    @api.depends("picking_time_ids")
    def _compute_time_elapsed(self):
        """
        This function calculate total time of operation with the lines of picking_time_ids
        """
        for record in self:
            start_time = False
            pause_time = False
            end_time = False
            for line in record.picking_time_ids:
                if line.type == "start":
                    start_time = line.create_date
                if line.type == "end":
                    end_time = line.create_date

            record.operation_start_date = start_time
            record.operation_pause_date = pause_time
            record.operation_end_date = end_time

            if record.operation_start_date and record.operation_end_date:
                record.total_time_elapsed = (
                    record.operation_end_date - record.operation_start_date
                ).total_seconds() / 60
            else:
                record.total_time_elapsed = False

    def button_validate(self):
        res = super().button_validate()
        for record in self:
            if res == True:
                user = record.env["res.users"].browse(record._context.get("uid", 1))
                record.env["stock.picking.time"].create(
                    {"pick_id": record.id, "employee_id": user.employee_id.id, "type": "end"}
                )

                if record.type_delivery_step == "out":
                    record.cart_id.pick_id = False
                    record.cart_id.out_id = False
                    record.cart_id.pack_id = False

                    new_pick = self.search([("picker_id", "=", False)], limit=1)
                    if new_pick:
                        new_pick.picker_id = record.picker_id.id

                    order = self.env["sale.order"].search([("name", "=", record.origin)])
                    wizard = self.env["sale.advance.payment.inv"].create(
                        {"sale_order_ids": order.ids, "advance_payment_method": "delivered"}
                    )
                    wizard._create_invoices(wizard.sale_order_ids)

        return res

    @api.depends("operation_start_date", "operation_pause_date", "operation_end_date", "state")
    def _compute_operation_state(self):
        for picking in self:
            if picking.operation_state in ["ready", "paused"] and picking.operation_start_date:
                picking.operation_state = "in_process"
                return
            if picking.operation_state == "in_process" and picking.operation_pause_date:
                picking.operation_state = "paused"
                return
            if picking.operation_state == "in_process" and (
                picking.operation_end_date or picking.state == "done"
            ):
                picking.operation_state = "finished"
                return

            if picking.state == "done":
                picking.operation_state = "finished"
                return
            if picking.state == "cancel":
                picking.operation_state = "cancel"
                return

    def action_confirm(self):
        res = super().action_confirm()
        for record in self:
            if record.type_delivery_step == "pick":
                record.picker_id = record.get_available_picker()
        return res

    def get_available_picker(self):
        picker_ids = self.env["hr.employee"].search([("role_picking", "=", "picker")])
        for picker in picker_ids:
            if picker.available_to_assing_picking():
                return picker.id
        return False
