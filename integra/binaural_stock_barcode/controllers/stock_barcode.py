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

        if cart_picking.pick_id and cart_picking.pick_id.state != "done":
            return {"action": cart_picking.pick_id.action_open_picking_client_action()}

        if (
            cart_picking.pick_id
            and cart_picking.out_id
            and cart_picking.pick_id.state == "done"
            and cart_picking.out_id.state != "done"
        ):
            request.env["stock.picking.time"].create(
                {
                    "pick_id": cart_picking.out_id.id,
                    "employee_id": user_id.employee_id.id,
                    "type": "start",
                }
            )
            return {"action": cart_picking.out_id.action_open_picking_client_action()}

        picking_id = user_id.employee_id.pick_ids.filtered(
            lambda x: x.operation_state in ["ready", "in_process"]
        )
        if picking_id:
            out_id = request.env["stock.picking"].search(
                ["&", ("origin", "=", picking_id.origin), ("type_delivery_step", "=", "out")]
            )
            cart_picking.write({"pick_id": picking_id.id, "out_id": out_id.id})
            request.env["stock.picking.time"].create(
                {"pick_id": picking_id.id, "employee_id": user_id.employee_id.id, "type": "start"}
            )

            return {"action": picking_id.action_open_picking_client_action()}

        return {"warning": _("You do not currently have a pick assigned")}
