from odoo.http import request
from odoo import fields, http
from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery


class BinauralWebsiteSaleDelivery(WebsiteSaleDelivery):

    def _update_website_sale_delivery_return(self, order, **post):
        res = super()._update_website_sale_delivery_return(order, **post)
        if order:
            Monetary = request.env["ir.qweb.field.monetary"]
            res["new_foreign_total_billed"] = (
                Monetary.value_to_html(
                    order.foreign_total_billed, {"display_currency": order.foreign_currency_id}
                ),
            )
        return res
