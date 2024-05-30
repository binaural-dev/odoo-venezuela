from odoo.http import request
from odoo import fields, http
from werkzeug.exceptions import NotFound
from odoo.tools.json import scriptsafe as json_scriptsafe
from odoo.addons.payment import utils as payment_utils
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from odoo.addons.http_routing.models.ir_http import slug
import logging

_logger = logging.getLogger(__name__)

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
        Returns a list of products that do not have availability for the given order.

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
            quantities_dict = line.product_id.with_context(
                warehouse=request.website.sudo().warehouse_id.id
            )._compute_quantities_dict(None, None, None)[line.product_id.id]
            quantity_available = quantities_dict["qty_available"] - quantities_dict["outgoing_qty"]
            if quantity_available - line.product_uom_qty < 0:
                errors.append({"product": line.product_id.name, "qty": str(quantity_available)})

        return errors

    @http.route(["/shop/cart"], type="http", auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive="", **post):
        """
        Ensure that the cart template is rendered with the corresponding errors if there are some.

        If there are not errors calls the original method.
        """
        if request.env.user._is_public():
            return request.redirect('/web/login')
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

    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        res = super().shop_payment_confirmation(**post)
        website = request.env['website'].get_current_website()
        company = request.env["res.company"].search(
            [
                ("id","=",website._get_cached('company_id'))
            ]
        )
        if company.budget_send:
            order = res.qcontext['order']
            order.update({
                "state": "sent",
            })
        return res

    def sitemap_shop(env, rule, qs):
        if not qs or qs.lower() in "/shop":
            yield {"loc": "/shop"}

        Category = env["product.public.category"]
        dom = sitemap_qs2dom(qs, "/shop/category", Category._rec_name)
        dom += env["website"].get_current_website().website_domain()
        for cat in Category.search(dom):
            loc = "/shop/category/%s" % slug(cat)
            if not qs or qs.lower() in loc:
                yield {"loc": loc}

    @http.route(
        [
            "/shop",
            "/shop/page/<int:page>",
            '/shop/category/<model("product.public.category"):category>',
            '/shop/category/<model("product.public.category"):category>/page/<int:page>',
        ],
        type="http",
        auth="public",
        website=True,
        sitemap=sitemap_shop,
    )
    def shop(
        self, page=0, category=None, search="", min_price=0.0, max_price=0.0, ppg=False, **post
    ):
        res = super().shop(page, category, search, min_price, max_price, ppg, **post)

        company_count = request.env["res.company"].sudo().search_count([])        
        if company_count > 1:
            website = request.env['website'].get_current_website()
            website_company_id = website._get_cached('company_id')
            products = res.qcontext['products'].filtered(
                lambda p: p.company_id.id == website_company_id
            )
            search_product = res.qcontext['search_product'].filtered(
                lambda p: p.company_id.id == website_company_id
            )
            res.qcontext.update({
                "products": products,
                "search_product": search_product,
                "search_count": len(search_product),
            })
        return res

    def _get_search_order(self, post):
        # OrderBy will be parsed in orm and so no direct sql injection
        # id is added to be sure that order is a unique sort key
        order = 'quantity desc'
        return 'is_published desc, %s' % order

    @http.route(["/shop/cart/update_json"],type="json",auth="public",methods=["POST"],website=True,csrf=False,)
    def cart_update_json(
        self, product_id, line_id=None, add_qty=None, set_qty=None, display=True,
        product_custom_attribute_values=None, no_variant_attribute_values=None, **kw
    ):
        if request.env.user._is_public():
            return NotFound()
        
        order = request.website.sale_get_order(force_create=True)
        if order.state != "draft":
            request.website.sale_reset()
            if kw.get("force_create"):
                order = request.website.sale_get_order(force_create=True)
            else:
                return {}

        if product_custom_attribute_values:
            product_custom_attribute_values = json_scriptsafe.loads(
                product_custom_attribute_values
            )

        if no_variant_attribute_values:
            no_variant_attribute_values = json_scriptsafe.loads(
                no_variant_attribute_values
            )

        values = order._cart_update(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw
        )

        for line in order.order_line:
            if line.product_id.id == product_id:
                product_qty_available = line.product_id.quantity
                order_line_qty = line.product_uom_qty

                if add_qty:
                    add_qty = (
                        add_qty
                        if add_qty <= product_qty_available
                        else product_qty_available
                    )

                if set_qty:
                    set_qty = min(set_qty, product_qty_available)

                line.update({"product_uom_qty": add_qty if add_qty else set_qty})

        request.session["website_sale_cart_quantity"] = order.cart_quantity

        if not order.cart_quantity:
            request.website.sale_reset()
            return values

        values["cart_quantity"] = order.cart_quantity
        values["minor_amount"] = (
            payment_utils.to_minor_currency_units(
                order.amount_total, order.currency_id
            ),
        )
        values["amount"] = order.amount_total

        if not display:
            return values

        values["website_sale.cart_lines"] = request.env["ir.ui.view"]._render_template(
            "website_sale.cart_lines",
            {
                "website_sale_order": order,
                "date": fields.Date.today(),
                "suggested_products": order._cart_accessories(),
            },
        )
        values["website_sale.short_cart_summary"] = request.env[
            "ir.ui.view"
        ]._render_template(
            "website_sale.short_cart_summary",
            {
                "website_sale_order": order,
            },
        )
        return values
