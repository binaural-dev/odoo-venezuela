import json
import logging
from datetime import datetime

from odoo import _, http
from odoo.addons.binaural_mobile.controllers import utils
from odoo.addons.binaural_mobile.controllers.sale_order_budget import SaleOrderBudget
from odoo.http import request

_logger = logging.getLogger(__name__)

class SaleOrderBudget(SaleOrderBudget):

    def _get_warehouse(self):
        main_warehouse_id = None
        use_main_warehouse = request.env.company.use_main_warehouse
        user_warehouse_id = request.env.user.property_warehouse_id
        
        if use_main_warehouse:
            main_warehouse_id = request.env.company.main_warehouse_id

        warehouse_id = user_warehouse_id or main_warehouse_id

        return warehouse_id

    def _get_data_after_edit_order_warehouse(self, data):
        warehouse_id = self._get_warehouse()

        if not warehouse_id:
            return data

        pre_response = data.get("data", False)

        if not pre_response:
            return data

        pre_response_item = pre_response[0]

        id_order = pre_response_item.get("id", False)

        order_id = utils.browse_model_data("sale.order", id_order)

        if not order_id:
            return data

        order_id.sudo().write({
            "warehouse_id": warehouse_id.id,
        })
        
        return data

    @http.route(
        "/budget/order/create",
        type="json",
        methods=["POST", "PUT"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def create_sale_order(self, **kwargs):
        data = super().create_sale_order(**kwargs)

        data = self._get_data_after_edit_order_warehouse(data)

        return data