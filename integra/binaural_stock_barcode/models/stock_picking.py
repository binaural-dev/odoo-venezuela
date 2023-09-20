from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    picker_id = fields.Many2one("res.users", string="Picker")
    operation_start_date = fields.Datetime(readonly=True, store=True)
    operation_pause_date = fields.Datetime()
    operation_end_date = fields.Datetime(readonly=True, store=True)
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
        picker_ids = self.env["res.users"].search([("role_picking", "=", "picker")])
        for picker in picker_ids:
            if picker.available_to_assing_picking():
                return picker.id
        return False
