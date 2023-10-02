from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    picker_id = fields.Many2one("hr.employee", string="Picker")
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
                time_elapsed = record.operation_end_date - record.operation_start_date
                _logger.info(time_elapsed)

    def button_validate(self):
        res = super().button_validate()
        user = self.env["res.users"].browse(self._context.get("uid", 1))
        self.env["stock.picking.time"].create(
            {"pick_id": self.id, "employee_id": user.employee_id.id, "type": "end"}
        )
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            picking_type = vals.get("picking_type_id", False)
            if (
                picking_type
                and self.env["stock.picking.type"].browse(picking_type)._get_type_steps() == "pick"
            ):
                vals.update({"picker_id": self.get_available_picker()})
        res = super().create(vals_list)
        return res

    def get_available_picker(self):
        picker_ids = self.env["hr.employee"].search([("role_picking", "=", "picker")])
        for picker in picker_ids:
            if picker.available_to_assing_picking():
                return picker.id
        return False
