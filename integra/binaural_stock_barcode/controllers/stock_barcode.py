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
        res = super(StockBarcodeControllerInherit, self).main_menu(barcode, **kw)
        barcode_type = None
        if not barcode_type or barcode_type == "cart":
            ret_open_cart_picking = self._try_open_cart_picking(barcode)
            if ret_open_cart_picking:
                return ret_open_cart_picking

        return res

    def _try_open_cart_picking(self, barcode):
        cart_picking = request.env["stock.picking.cart"].search(
            [
                ("barcode", "=", barcode),
            ],
            limit=1,
        )
        user_id = request.env["res.users"].browse(request.context.get("uid", 1))
        picking_id = user_id.employee_id.pick_ids
        if picking_id:
            cart_picking.write({"pick_id": picking_id.id})
            request.env["stock.picking.time"].create(
                {"pick_id": picking_id.id, "employee_id": user_id.employee_id.id, "type": "start"}
            )
            action = picking_id.action_open_picking_client_action()
            return {"action": action}
        return False
