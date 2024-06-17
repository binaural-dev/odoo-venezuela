import logging

from odoo import _, http
from odoo.addons.binaural_mobile.controllers import utils
from odoo.addons.binaural_mobile.controllers.sale_order_budget import (
    FIELD_ORDER_LINE,
    FIELDNAMES,
    PARSE_FIELDS,
    SaleOrderBudget,
)
from odoo.http import request

_logger = logging.getLogger(__name__)

class SaleOrderBudget(SaleOrderBudget):

    @http.route("/settings/read", type="json", methods=["POST"], auth="public", website=False, sitemap=False)
    def get_settings(self, **kwargs):
        dict_settings = super().get_settings()
        company_id = request.env.company

        dict_settings["is_active_multi_packaging"] = company_id.use_multiple_packaging

        return dict_settings
    
    @http.route(
        "/budget/create/order/line",
        type="json",
        methods=["POST", "PUT"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def create_sale_order_lines(self, **kwargs):
        company_id = request.env.company

        for key, value in kwargs.items():
            if value == type(str):
                kwargs[key] = int(value)
        
        data = {"status": 200, "msg": _("Success")}

        sale_orders = kwargs.get("sale_orders", [])
        
        is_active_multi_packaging = company_id.use_multiple_packaging
        
        for sale_order in sale_orders:
            sale_order = sale_order["sale_order_id"]
            if utils.product_duplicate(sale_order) and not is_active_multi_packaging:
                data.update({"status": 400, "msg": _("There are duplicated products.")})
                return data
            tax_included = self._get_tax_included(kwargs)
            sale_order["tax_included"] = tax_included
            sale_id = sale_order.pop("id", False)

            request.update_env(user=request.session.uid)

            if sale_id:
                try:
                    new_lines = []
                    products_ids_order = []
                    sale = utils.browse_model_data("sale.order", sale_id)

                    if sale and sale_order.get("order_line", False):
                        products_ids_order = sale.order_line.mapped("product_id").ids
                        lines = sale_order.get("order_line")

                        def product_id_exist(line):
                            product_id = line.get("product_id")
                            return product_id not in products_ids_order
                        
                        new_lines = [line for line in lines if line.get("product_id")]
                        new_lines = list(filter(product_id_exist, new_lines))
                        
                        if not len(new_lines):
                            sale_json = sale.read(FIELDNAMES)
                            sale_json = utils.convert_field_string(sale_json, PARSE_FIELDS)
                            sale_json = utils.get_order_line(sale_json, FIELD_ORDER_LINE)
                            data.update({"status": 200, "msg": "msg", "data": sale_json})
                        
                        write_lines = utils.set_order_line(sale_order, tax_included)

                        if write_lines:
                            sale_order["order_line"] = write_lines
                            sale.write(sale_order)
                            sale_json = sale.read(FIELDNAMES)
                            if sale_json:
                                sale_json = utils.convert_field_string(sale_json, PARSE_FIELDS)
                                sale_json = utils.get_order_line(sale_json, FIELD_ORDER_LINE)
                                data.update({"data": sale_json})
                        else:
                            data.update(
                                {
                                    "status": 400,
                                    "msg": _("There was an error adding lines to the sale order."),
                                }
                            )
                except Exception as e:
                    data.update({"status": 400, "msg": str(e)})
                    return data
        return data
