# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import http, _
from odoo.http import request
from odoo.modules.module import get_resource_path
from odoo.osv import expression
from odoo.tools import pdf, split_every
from odoo.tools.misc import file_open
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController


class StockBarcodeControllerInherit(StockBarcodeController):
    @http.route("/stock_barcode/scan_from_main_menu", type="json", auth="user")
    def main_menu(self, barcode, **kw):
        res = super().main_menu(barcode, **kw)
        barcode_type = None

        cart_rule = [
            rule
            for rule in self._get_barcode_nomenclature().get("barcode.rule", [])
            if rule["type"] == "cart"
        ]

        if not barcode_type or barcode_type == "cart":
            ret_open_cart_picking = self._try_open_cart_picking(barcode)
            if ret_open_cart_picking:
                return ret_open_cart_picking
            elif barcode.startswith(cart_rule[0].get("pattern", "818")):
                return {
                    "warning": _("No cart corresponding to barcode %(barcode)s")
                    % {"barcode": barcode}
                }

        return res

    def _try_open_cart_picking(self, barcode):
        """ """
        cart_picking = request.env["stock.picking.cart"].search(
            [
                ("barcode", "=", barcode),
            ],
            limit=1,
        )

        if not cart_picking:
            return False

        user_id = request.env["res.users"].browse(request.context.get("uid", 1))
        employee_id = user_id.employee_id
        role_picking = user_id.role_picking

        operations = cart_picking.pick_id + cart_picking.out_id + cart_picking.pack_id

        if operations:
            # verify if the employee has access to open picking in state 'assigned'
            # Picker == Pick
            # Packer == Pack
            # Out == Out
            assigned_operation = operations.filtered(
                lambda operation: operation.state == "assigned"
            )
            if not assigned_operation:
                return {"warning": _("There are not picking available to open")}

            if not self.available_to_open_picking(assigned_operation):
                return {
                    "warning": _(
                        "You cannot take a cart if the picker has not finished his operation"
                    )
                }

            if assigned_operation.picker_id and assigned_operation.picker_id != employee_id:
                return {"warning": _("The pick is already assigned to another picker")}

            in_process = employee_id.pick_ids.filtered(lambda x: x.operation_state == "in_process")

            if in_process and in_process != assigned_operation:
                return {"warning": _("You have another operation in process")}

            if assigned_operation.operation_state == "ready":
                assigned_operation.set_time_operation("start", employee_id)
                assigned_operation.write({"cart_id": cart_picking.id, "picker_id": employee_id.id})
            else:
                assigned_operation.set_time_operation("resume", employee_id)

            return self._open_stock_picking(assigned_operation)

        # Init Process Assign Cart
        picking_id = self.get_pick_assigned(employee_id)

        if picking_id:
            if picking_id.cart_id and picking_id.cart_id != cart_picking:
                return {"warning": _("The pick is already assigned to another cart")}

            cart_picking.write(
                {
                    "out_id": picking_id._get_outs(assigned=True),
                    "pick_id": picking_id._get_picks(assigned=True),
                    "pack_id": picking_id._get_packs(assigned=True),
                }
            )
            picking_id.write({"cart_id": cart_picking.id})
            picking_id.set_time_operation("start", employee_id)
            return self._open_stock_picking(picking_id)

        return {"warning": _("You do not currently have a pick assigned")}

    def available_to_open_picking(self, picking):
        user_id = request.env["res.users"].browse(request.context.get("uid", 1))
        role_picking = user_id.role_picking
        if picking.type_delivery_step == "pick" and role_picking != "picker":
            return False
        if picking.type_delivery_step == "pack" and role_picking != "packer":
            return False
        if picking.type_delivery_step == "out" and role_picking != "out":
            return False
        return True

    def _open_stock_picking(self, stock_picking):
        return {"action": stock_picking.action_open_picking_client_action()}

    def start_time_operation(self, picking_id, employee_id):
        model_stock_picking_time = request.env["stock.picking.time"]
        model_stock_picking_time.create(
            {"pick_id": picking_id.id, "employee_id": employee_id.id, "type": "start"}
        )
        return model_stock_picking_time

    def get_pick_assigned(self, employee_id):
        return employee_id.pick_ids.filtered(lambda x: x.operation_state in ["ready", "in_process"])
