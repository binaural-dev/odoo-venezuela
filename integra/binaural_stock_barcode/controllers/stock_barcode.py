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

import logging

_logger = logging.getLogger(__name__)


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

        if role_picking == "picker":
            if not self.is_cart_available_to_assign(cart_picking):
                return {
                    "warning": _(
                        "You cannot assign the pick to this cart because there is an OUT in process"
                    )
                }
            if cart_picking.pick_id and cart_picking.pick_id.state != "done":
                return self._open_stock_picking(cart_picking.pick_id)

            picking_id = self.get_pick_assigned(employee_id)

            if picking_id:
                out_id = model_stock_picking.search(
                    ["&", ("origin", "=", picking_id.origin), ("type_delivery_step", "=", "out")]
                )
                picking_id.write({"cart_id": cart_picking.id})
                cart_picking.write({"pick_id": picking_id.id, "out_id": out_id.id})

                self.start_time_operation(picking_id, employee_id)
                return self._open_stock_picking(picking_id)

            return {"warning": _("You do not currently have a pick assigned")}

        if role_picking == "out":
            if cart_picking.pick_id and cart_picking.pick_id.state != "done":
                return {
                    "warning": _(
                        "You cannot take a cart if the picker has not finished his operation"
                    )
                }

            if self.is_cart_available_open_out(cart_picking):
                self.start_time_operation(cart_picking.out_id, employee_id)
                cart_picking.out_id.write({"cart_id": cart_picking.id, "picker_id": employee_id.id})
                return self._open_stock_picking(cart_picking.out_id)

            return {"warning": _("This cart does not have any OUT assigned")}

        return {
            "warning": _(
                "Your user is not configured with any role to be able to take an operation"
            )
        }

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
        if not cart.pick_id and not cart.out_id:
            return True

        if (
            cart.pick_id
            and cart.pick_id.state != "done"
            and cart.out_id
            and cart.out_id.state != "done"
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
