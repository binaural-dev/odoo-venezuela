from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    role_picking = fields.Selection(related="user_id.role_picking", readonly=False)

    supervisor_barcode_password = fields.Char(
        related="user_id.supervisor_barcode_password", readonly=False
    )
    pick_ids = fields.One2many(
        "stock.picking",
        "picker_id",
        domain=[("operation_state", "in", ["ready", "in_process", "paused"])],
    )

    cart_active_id = fields.Many2one("stock.picking.cart", compute="_compute_cart_active_id")
    pending_pick_id = fields.Many2one(
        "stock.picking",
        compute="_compute_pick_state_id",
        inverse="inverse_pending_pick_id",
    )
    active_pick_id = fields.Many2one("stock.picking", compute="_compute_pick_state_id")
    paused_pick_ids = fields.Many2many("stock.picking", compute="_compute_pick_state_id")

    def pause_operation(self):
        self.active_pick_id.set_time_operation("pause")

    def get_pick_states(self):
        return {
            "paused_pick_ids": self.pick_ids.filtered(lambda x: x.operation_state == "paused"),
            "pending_pick_id": self.pick_ids.filtered(lambda x: x.operation_state == "ready"),
            "active_pick_id": self.pick_ids.filtered(lambda x: x.operation_state == "in_process"),
        }

    def remove_picking_from_employee(self, picking_id):
        """
        This function removes the picking from the employee
        """
        self.pick_ids -= picking_id

    @api.depends("pick_ids.operation_state")
    def _compute_pick_state_id(self):
        for record in self:
            values = record.get_pick_states()
            record.active_pick_id = values.get("active_pick_id")
            record.pending_pick_id = values.get("pending_pick_id")
            record.paused_pick_ids = values.get("paused_pick_ids")

    def inverse_pending_pick_id(self):
        for record in self:
            values = record.get_pick_states()

            if not record.pending_pick_id and values.get("pending_pick_id", False):
                record.remove_picking_from_employee(values["pending_pick_id"])

            if values.get("active_pick_id", False):
                raise ValidationError(
                    _("You cannot assign a pending pick if you have an active pick")
                )

            if record.pending_pick_id.picker_id:
                record.pending_pick_id.picker_id = False

            if record.pending_pick_id:
                pick_ids = record.pick_ids.filtered(lambda x: x.operation_state != "ready")
                pick_ids |= record.pending_pick_id
                record.pick_ids = pick_ids

    @api.depends("pick_ids", "active_pick_id")
    def _compute_cart_active_id(self):
        for record in self:
            if record.active_pick_id:
                record.cart_active_id = record.active_pick_id.cart_id
                continue
            record.cart_active_id = False

    def available_to_assing_picking(self):
        """
        This function checks if the picker is available to be assigned a pick, checking if it is
        not in a pick in progress
        """
        if len(self.pick_ids.filtered(lambda x: x.operation_state in ["ready", "in_process"])) == 0:
            return True
        return False
