from odoo.http import request
from odoo import fields, http
from werkzeug.exceptions import NotFound

from odoo.addons.website_sale.controllers.main import WebsiteSale


class BinauralWebsiteSale(WebsiteSale):
    # TODO Arreglar campo de ciudad, no se esta guardando ni en el formulario del usuario ni en el
    # Formulario de dirección antes de confirmar un pedido.
    def _get_mandatory_fields_billing(self, country_id=False):
        req = ["name", "email", "street", "country_id", "vat", "phone"]
        if country_id:
            country = request.env["res.country"].browse(country_id)
            if country.state_required:
                req += ["state_id"]
        return req

    def _get_mandatory_fields_shipping(self, country_id=False):
        req = ["name", "street", "country_id", "vat", "phone"]
        if country_id:
            country = request.env["res.country"].browse(country_id)
            if country.state_required:
                req += ["state_id"]
        return req

    @http.route(["/shop/checkout"], type="http", auth="public", website=True, sitemap=False)
    def checkout(self, **post):
        """
        Checks if there are errors on the current order and, if that's the case, calls the cart
        method with the corresponding errors.
        """
        order = request.website.sale_get_order()

        values = {"website_sale_order": order, "date": fields.Date.today()}

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            return request.redirect("/shop/address")

        redirection = self.checkout_check_address(order)
        if redirection:
            return redirection

        values = self.checkout_values(**post)
        values["error"] = {"error_message": "Error"}
        errors = self._get_checkout_errors(order)
        if errors:
            return self.cart(errors=errors)

        if post.get("express"):
            return request.redirect("/shop/confirm_order")

        values.update({"website_sale_order": order})

        # Avoid useless rendering if called in ajax
        if post.get("xhr"):
            return "ok"
        return request.render("website_sale.checkout", values)

    def _get_checkout_errors(self, order):
        """
        Returns a list of products that does not have availability for the given order.

        Parameters
        ----------
        order : sale.order
            The order for which products quantity availability is gonna be checked

        Returns
        -------
        list(dict)
            The list of products with its available quantity
        """
        errors = []
        for line in order.order_line:
            quantity_available = line.product_id.get_available_quantity_by_warehouse(
                request.website.sudo().warehouse_id
            )
            if quantity_available - line.product_uom_qty < 0:
                errors.append({"product": line.product_id.name, "qty": str(quantity_available)})

        return errors

    @http.route(["/shop/cart"], type="http", auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive="", **post):
        """
        Ensure that the cart template is rendered with the corresponding errors if there are some.

        If there are not errors calls the original method.
        """
        errors = post.get("errors", False)
        if not errors:
            return super().cart(access_token=access_token, revive=revive, **post)
        order = request.website.sale_get_order()
        if order and order.state != "draft":
            request.session["sale_order_id"] = None
            order = request.website.sale_get_order()

        request.session["website_sale_cart_quantity"] = order.cart_quantity

        values = {}
        if access_token:
            abandoned_order = (
                request.env["sale.order"]
                .sudo()
                .search([("access_token", "=", access_token)], limit=1)
            )
            if not abandoned_order:  # wrong token (or SO has been deleted)
                raise NotFound()
            if abandoned_order.state != "draft":  # abandoned cart already finished
                values.update({"abandoned_proceed": True})
            elif revive == "squash" or (
                revive == "merge" and not request.session.get("sale_order_id")
            ):  # restore old cart or merge with unexistant
                request.session["sale_order_id"] = abandoned_order.id
                return request.redirect("/shop/cart")
            elif revive == "merge":
                abandoned_order.order_line.write({"order_id": request.session["sale_order_id"]})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session.get(
                "sale_order_id"
            ):  # abandoned cart found, user have to choose what to do
                values.update({"access_token": abandoned_order.access_token})

        values.update(
            {
                "website_sale_order": order,
                "date": fields.Date.today(),
                "errors": errors,
                "suggested_products": [],
            }
        )
        if order:
            order.order_line.filtered(lambda l: not l.product_id.active).unlink()
            values["suggested_products"] = order._cart_accessories()
            values.update(self._get_express_shop_payment_values(order))

        if post.get("type") == "popover":
            # force no-cache so IE11 doesn't cache this XHR
            return request.render(
                "website_sale.cart_popover", values, headers={"Cache-Control": "no-cache"}
            )

        return request.render("website_sale.cart", values)
