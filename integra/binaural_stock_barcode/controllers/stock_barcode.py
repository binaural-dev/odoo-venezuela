# -*- coding: utf-8 -*-
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

        model_stock_picking = request.env["stock.picking"]

        type_delivery_step = request.env.company.main_warehouse_id.delivery_steps

        init_operation = cart_picking.pick_id
        if type_delivery_step == "ship_only":
            init_operation = cart_picking.out_id

        if type_delivery_step != "ship_only" and role_picking == "out":
            if cart_picking.pick_id and cart_picking.pick_id.state != "done":
                return {
                    "warning": _(
                        "You cannot take a cart if the picker has not finished his operation"
                    )
                }

            if self.is_cart_available_open_out(cart_picking):
                cart_picking.out_id.set_time_operation("start", employee_id)
                cart_picking.out_id.write({"cart_id": cart_picking.id, "picker_id": employee_id.id})
                return self._open_stock_picking(cart_picking.out_id)

            return {"warning": _("This cart does not have any OUT assigned")}

        # Init Process Assign Cart

        if not self.is_cart_available_to_assign(cart_picking):
            return {
                "warning": _(
                    "You cannot assign the pick to this cart because there is an operation in process"
                )
            }

        if init_operation and init_operation.state != "done":
            if init_operation.operation_state == "paused":
                if init_operation.picker_id.pick_ids.filtered(
                    lambda x: x.operation_state in ["in_process"]
                ):
                    return {"warning": _("You have another operation in process")}
                init_operation.set_time_operation("resume")

            if init_operation.picker_id != employee_id:
                return {"warning": _("The pick is already assigned to another picker")}

            return self._open_stock_picking(init_operation)

        picking_id = self.get_pick_assigned(employee_id)

        if picking_id:
            if picking_id.cart_id:
                return {"warning": _("The pick is already assigned to another cart")}

            if type_delivery_step == "ship_only":
                cart_picking.write({"out_id": picking_id.id})
            else:
                out_id = model_stock_picking.search(
                    ["&", ("origin", "=", picking_id.origin), ("type_delivery_step", "=", "out")]
                )
                cart_picking.write({"pick_id": picking_id.id, "out_id": out_id.id})
                if type_delivery_step == "pick_pack_ship":
                    cart_picking.write({"pack_id": picking_id.pack_id.id})

            picking_id.write({"cart_id": cart_picking.id})
            picking_id.set_time_operation("start", employee_id)
            return self._open_stock_picking(picking_id)

        return {"warning": _("You do not currently have a pick assigned")}

    def is_cart_available_open_out(self, cart):
        if (
            cart.pick_id
            and cart.out_id
            and cart.pick_id.state == "done"
            and cart.out_id.state != "done"
        ):
            return True
        return False

    def is_cart_available_to_assign(self, cart):
        if True not in (bool(cart.pick_id), bool(cart.out_id), bool(cart.pack_id)):
            return True

        type_delivery_step = request.env.company.main_warehouse_id.delivery_steps
        if type_delivery_step == "ship_only" and cart.out_id and cart.out_id.state != "done":
            return True
        if (
            type_delivery_step == "pick_ship"
            and cart.pick_id
            and cart.pick_id.state != "done"
            and cart.out_id
            and cart.out_id.state != "done"
        ):
            return True
        if (
            type_delivery_step == "pick_pack_ship"
            and cart.pick_id
            and cart.pick_id.state != "done"
            and cart.out_id
            and cart.out_id.state != "done"
            and cart.pack_id
            and cart.pack_id.state != "done"
        ):
            return True
        return False

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
