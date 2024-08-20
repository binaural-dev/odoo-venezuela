import json
import logging
from datetime import datetime

from odoo import _, http
from odoo.http import request
from odoo.osv import expression

from . import utils

_logger = logging.getLogger(__name__)

SALE_STATES = ["draft", "sent"]
FIELDNAMES = [
    "id",
    "name",
    "partner_id",
    "partner_invoice_id",
    "partner_shipping_id",
    "validity_date",
    "date_order",
    "tax_included",
    "pricelist_id",
    "payment_term_id",
    "order_line",
    "amount_untaxed",
    "amount_tax",
    "amount_total",
    "state",
    "note",
    "invoice_status",
    "state_seller",
]
FIELD_ORDER_LINE = [
    "id",
    "product_template_id",
    "name",
    "product_uom_qty",
    "price_unit",
    "price_unit_with_tax",
    "price_total",
    "tax_id",
    "price_subtotal",
    "product_id",
]
FIELDFILTERS = ["id", "name", "amount_tax", "amount_untaxed", "amount_total", "state"]
PARSE_FIELDS = ["validity_date", "date_order"]


class SaleOrderBudget(http.Controller):

    def _get_tax_included(self, kwargs):
        company = request.env.company
        is_optional_tax_included = company.dairy_fiscal and company.dairy_no_fiscal

        if is_optional_tax_included:
            return kwargs.get("tax_included", False)

        return any(company.dairy_fiscal)
    
    def _get_vals_write_order_line(self, kwargs):
        vals = utils.filter_dict(kwargs, ["product_id", "product_uom_qty", "tax_id"])

        if "tax_include" not in vals:
            return vals

        tax_id = search_model_data("account.tax", domain, 1).id
        tax_include = self._get_tax_included(kwargs)

        if tax_included or request.env.company.mobile_tax_include:
            product_taxes_id = browse_model_data("product.product", product_id).taxes_id

            if any(product_taxes_id):
                tax_id =  product_taxes_id[0].id

        vals["tax_id"] = tax_id
        
        return vals

    def _check_write_order_line(self, line_id):
        if not line_id:
            return {"status": 400, "msg": "id argument missing", "data": None}
        
        order_line_id = utils.browse_model_data("sale.order.line", int(line_id))

        if not order_line_id:
            return {"status": 404, "msg": (_("Line record not Found with id %s") % line_id), "data": None}

        order_state = order_line_id.order_id.state

        if order_state != 'draft':
            return {"status": 400, "msg": (_('The order with status "%s" cannot be edited') % order_state.upper()), "data": None}

        return False

    @http.route("/settings/read", type="json", methods=["POST"], auth="public", website=False, sitemap=False)
    def get_settings(self, **kwargs):
        allow_out_of_stock_order = request.env['res.config.settings'].sudo().get_values().get('allow_out_of_stock_order')  # Crear una instancia temporal de res.config.settings

        return {
            "allow_out_of_stock_order": allow_out_of_stock_order,
        }


    @http.route(
        "/budget/order", type="http", methods=["GET"], auth="public", website=False, sitemap=False
    )
    def get_sale_order(self, seller_id, limit=20, offset=0, partner_name=None, **kwargs):
        try:
            data = {"status": 200, "msg": _("Success")}
            _filter = [key for key in FIELDFILTERS if kwargs.get(key)]
            domain_partner = expression.AND(
                [
                    [
                        ("seller_id", "=", int(seller_id)),
                        ("type", "=", "contact")
                    ]
                ]
            )

            if partner_name:
                domain_partner_name = utils.get_search_domain(FIELDFILTERS[1], partner_name)
                domain_partner = expression.AND([domain_partner, domain_partner_name])
            partner_ids = utils.search_model_data("res.partner", domain_partner).ids

            domain = expression.AND(
                [
                    [
                        ("state", "in", ["draft", "sent", "sale", "done"]),
                        ("partner_id", "in", partner_ids),
                    ]
                ]
            )
            if kwargs.get(FIELDFILTERS[1], False):
                search_domain = utils.get_search_domain(
                    FIELDFILTERS[1], kwargs.get(FIELDFILTERS[1])
                )
                domain = expression.AND([domain, search_domain])
                _filter.remove(FIELDFILTERS[1])

            domain = expression.AND(
                [
                    domain,
                    [(key, "=", int(kwargs.get(key))) for key in _filter],
                ]
            )
            order_ids = utils.get_model_data(
                "sale.order", domain, FIELDNAMES, int(limit), int(offset)
            )
            all_sale_count = utils.get_model_count("sale.order", domain)

            sale_order_count = len(order_ids)
            if not sale_order_count:
                data.update(
                    {
                        "status": 204,
                        "msg": "No hay presupuestos asociados",
                        "count": 0,
                        "data": False,
                    }
                )
                return json.dumps(data)

            order_ids = utils.convert_field_string(order_ids, PARSE_FIELDS)
            order_ids = utils.get_order_line(order_ids, FIELD_ORDER_LINE)
            data.update(
                {"data": order_ids, "count": sale_order_count, "total_count": all_sale_count}
            )
        except Exception as e:
            data.update(
                {"status": 409, "msg": _("The request couldn't be complete due a source conflict.")}
            )
            return json.dumps(data)

        return json.dumps(data)

    @http.route(
        "/budget/confirm_or_cancel_order",
        type="json",
        methods=["POST","PUT"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def confirm_or_cancel_order(self, sale_id=False, confirm=False, uid=False, **kwargs):
        data = {"status": 200, "msg": _("Success")}
        try:
            if sale_id:
                sale = utils.browse_model_data("sale.order", sale_id)
                if confirm == "confirm":
                    success, msg = self.check_lines_validations_order(sale.order_line)
                    if not success:
                        data.update({"status": 400, "msg": msg})
                        return data
                    if sale.company_id.account_use_credit_limit and sale.partner_id.use_partner_credit_limit_order:
                        total_pay = sale.partner_id.credit + sale.amount_total
                        if total_pay > sale.partner_id.credit_limit:
                            decimal_places = sale.currency_id.decimal_places
                            data.update(
                                {
                                    "status": 400, 
                                    "msg": (_("La cuenta por cobrar del cliente es de %s más %s en presupuesto da un total de %s superando el límite de ventas de %s. Por favor cancele el presupuesto o comuníquese con el administrador para aumentar el límite de crédito del cliente.",
                                            round(sale.partner_id.credit, decimal_places), round(sale.amount_total, decimal_places), round(total_pay,decimal_places), round(sale.partner_id.credit_limit, decimal_places)))
                                }
                            )
                            return data
                    sale.action_confirm()
                elif confirm == "cancel":
                    sale.action_cancel()
                return data
        except Exception as e:
            data.update({"status": 400, "msg": e})
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
        kwargs = kwargs.get("order")
        for key, value in kwargs.items():
            if value == type(str):
                kwargs[key] = int(value)
        data = {"status": 200, "msg": "Success"}
        sale_order = kwargs.get("sale_order")
        tax_included = self._get_tax_included(kwargs)
        sale_order["tax_included"] = tax_included
        seller_id = request.env.user.employee_id.id
        request.update_env(user=request.session.uid)
        lines = utils.set_order_line(sale_order, tax_included)
        sale_order["order_line"] = lines
        sale_order.update({
            "date_order": datetime.today(),
            "seller_id": seller_id
            })

        sale = False
        try:
            sale = utils.create_record("sale.order", sale_order)
            
            data.update({"data": sale})
        except Exception as e:
            data.update({"status": 400, "msg": str(e)})
            return data

        if not sale:
            data.update(
                {
                    "status": 400,
                    "msg": _("There was an error creating the Sale Order"),
                    "count": 0,
                    "data": False,
                }
            )
            return data

        domain = [("id", "=", sale.id)]
        order_id = utils.get_model_data("sale.order", domain, fields=FIELDNAMES, limit=1)
        if order_id:
            order_id = utils.convert_field_string(order_id, PARSE_FIELDS)
            order_id = utils.get_order_line(order_id, FIELD_ORDER_LINE)
            data.update({"data": order_id})

        return data


    @http.route(
        "/budget/order/line/edit",
        type="json",
        methods=["POST"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def write_order_line(self,  **kwargs):
        line_id = kwargs.get('line_id', False)
        tax_include = kwargs.get('tax_include', False)
        is_bad_request_error = self._check_write_order_line(line_id)

        if is_bad_request_error:
            return is_bad_request_error

        try:
            vals = self._get_vals_write_order_line(kwargs)

            record = utils.update_record("sale.order.line", int(line_id), vals)

            data_response = record.read(FIELD_ORDER_LINE)

            return {"status": 200, "msg": "Success", "data": data_response}

        except Exception as e:
            return {
                "status": 400,
                "msg": str(e)
            }

    @http.route(
        "/budget/edit/order", type="json", methods=["PUT"], auth="public", website=False, sitemap=False
    )
    def edit_sale_order(self, **kwargs):

        validation_errors = utils.ValidateRequest.require([
            ["id"],
            ["order_line"],
            # ["user_id"]
        ], kwargs, "sale_order" )

        if any(validation_errors):
            return utils.ValidateRequest.json(validation_errors)
        
        data = {"status": 200, "msg": _("Success")}
        sale_order = kwargs.get("sale_order")
        tax_included = self._get_tax_included(kwargs)
        sale_order["tax_included"] = tax_included

        sale_id = int(sale_order.pop("id", False))
        order_line = sale_order.pop("order_line", False)

        try:
            if sale_id:
                domain = [("id", "=", sale_id)]
                sale = utils.search_model_data("sale.order", domain)
                if sale:
                    if tax_included:
                        order_line = self.include_product_tax(order_line)
                        sale_order["order_line"] = order_line
                    sale_order["order_line"] = utils.set_order_line(sale_order, tax_included)
                    sale.write(sale_order)
                    return data
            else:
                data.update({"status": 400, "msg": _("The Sale Order does not exist.")})
                return data
        except Exception as e:
            data.update({"status": 400, "msg": str(e)})
            return data
    
    def _get_product_packaging(self, product_id):
        company_user = request.env.company

        if not (product_id.packaged_product and company_user.group_stock_packaging):
            return []

        packaging_ids = product_id.packaging_ids

        if not packaging_ids:
            return []

        packages = []

        for packaging_id in packaging_ids:
            package = packaging_id.read(["id", "name", "qty", "product_uom_id", "sales", "purchase"])

            packages.extend(package)

        return packages
    
    def _get_product_uom(self, product_id):
        return product_id.uom_id.name

    @http.route("/budget/order/read", type="json", methods=["POST"], auth="public", website=False, sitemap=False)
    def read_order(self, **kwargs):
        validation_errors = utils.ValidateRequest.require([
            ["sale_id"],
        ], kwargs)

        if any(validation_errors):
            return utils.ValidateRequest.json(validation_errors)

        data = {"status": 200, "msg": _("Success")}
        sale_id = kwargs.get("sale_id", False)
        tax_included = self._get_tax_included(kwargs)

        try:
            sale = utils.browse_model_data("sale.order", int(sale_id))

            if not sale:
                data.update({"status": 404, "msg": _("No sale order were found.")})
                return data

            sale_order = sale.read(FIELDFILTERS)

            sale_order = utils.convert_field_string(sale_order, PARSE_FIELDS)

            sale_order = sale_order[0]

            sale_order["order_line"] = sale.order_line.filtered(lambda line: line.display_type == False).read(FIELD_ORDER_LINE)
            
            for order_line in sale_order["order_line"]:
                product_qty = request.env["product.template"].sudo().search([('id', '=', int(order_line["product_template_id"][0]))]).quantity
                product_id_id = int(order_line["product_id"][0])
                product_id = request.env["product.product"].browse([product_id_id])
                order_line["packaged_product"] = product_id.packaged_product
                order_line["qty_available"] = product_qty
                order_line["packaging_ids"] = self._get_product_packaging(product_id)
                order_line["uom"] = self._get_product_uom(product_id)

            if request.env.company.mobile_show_tax_type == "include_tax":
                for line in sale_order["order_line"]:
                    line["price_unit"] = line["price_unit_with_tax"]
                    line["price_subtotal"] = line["price_total"]

            for line in sale_order["order_line"]:
                description_tax = _("Tax no Selected")
                value_tax = 0
                if line["tax_id"][0]:
                    tax = request.env["account.tax"].search([("id","=", line["tax_id"][0])])
                    value_tax = tax.amount
                    description_tax = tax.description

                line["tax_id"].append(description_tax)
                line["tax_id"].append(value_tax)

            data.update({"data": sale_order})

            return data
        except Exception as e:
            data.update({"status": 409, "msg": _("There was an error handling the request"), "error": str(e)})
            return data

    @http.route("/budget/include_tax", type="json", methods=["POST"], auth="public", website=False, sitemap=False)
    def include_taxes_in_sale_order(self, **kwargs):
        validation_errors = utils.ValidateRequest.require([
            ["sale_id"],
            ["tax_included"],
        ], kwargs)
        
        if any(validation_errors):
            return utils.ValidateRequest.json(validation_errors)

        data = {"status": 200, "msg": _("Success")}
        sale_id = kwargs.get("sale_id", False)
        tax_included = self._get_tax_included(kwargs)
        note = kwargs.get("note", False)
        try:
            sale = utils.browse_model_data("sale.order", int(sale_id))
            if not sale:
                data.update({"status": 404, "msg": _("No sale order were found.")})
                return data

            sale_to_write = sale.read(["tax_included", "order_line"])
            sale_to_write = sale_to_write[0]

            sale_to_write["order_line"] = sale.order_line.read(FIELD_ORDER_LINE)
            sale_to_write["tax_included"] = tax_included
            sale_to_write["note"] = note
            sale_to_write["order_line"] = utils.set_order_line(sale_to_write, tax_included)

            sale.write(sale_to_write)

            sale_order = sale.read(FIELDFILTERS)

            sale_order = utils.convert_field_string(sale_order, PARSE_FIELDS)

            sale_order = sale_order[0]

            sale_order["order_line"] = sale.order_line.filtered(lambda line: line.display_type == False).read(FIELD_ORDER_LINE)
            
            for order_line in sale_order["order_line"]:
                product_qty = request.env["product.template"].sudo().search([('id', '=', int(order_line["product_template_id"][0]))]).quantity
                order_line["qty_available"] = product_qty
                order_line["packaging_ids"] = self._get_product_packaging(order_line)

            if request.env.company.mobile_show_tax_type == "include_tax":
                for line in sale_order["order_line"]:
                    line["price_unit"] = line["price_unit_with_tax"]
                    line["price_subtotal"] = line["price_total"]
            
            if tax_included:
                for line in sale_order["order_line"]:
                    description_tax = _("Tax no Selected")
                    value_tax = 0
                    if line["tax_id"][0]:
                        tax = request.env["account.tax"].search([("id","=", line["tax_id"][0])])
                        value_tax = tax.amount
                        description_tax = tax.description
                    line["tax_id"].append(description_tax)
                    line["tax_id"].append(value_tax)
            data.update({"data": sale_order})

            return data
        except Exception as e:
            data.update({"status": 409, "msg": _("There was an error handling the request"), "error": str(e)})
            return data

    @http.route("/validation_available", type="json", methods=["POST", "PUT"], auth="public", website=False, sitemap=False)
    def validation_available(self, **kwargs):
        allow_out_of_stock_order = request.env['res.config.settings'].sudo().get_values().get('allow_out_of_stock_order')
        return {"allow_out_of_stock_order": allow_out_of_stock_order}

    @http.route(
        "/budget/create/order/line",
        type="json",
        methods=["POST", "PUT"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def create_sale_order_lines(self, **kwargs):
        for key, value in kwargs.items():
            if value == type(str):
                kwargs[key] = int(value)
        
        data = {"status": 200, "msg": _("Success")}

        sale_orders = kwargs.get("sale_orders", [])
        
        for sale_order in sale_orders:
            sale_order = sale_order["sale_order_id"]
            if utils.product_duplicate(sale_order):
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

    @http.route("/budget/delete_line", type="json", auth="public", methods=["POST"], sitemap=False)
    def delete_order_line(self, sale_order_id, line_id, uid=False):
        data = {"status": 200, "msg": _("Success")}
        domain = [("id", "=", int(sale_order_id))]
        sale = utils.search_model_data("sale.order", domain).exists()
        
        if sale and sale.state in SALE_STATES:
            try:
                domain = [("id", "=", int(line_id)), ("order_id", "=", sale.id)]
                line = utils.search_model_data("sale.order.line", domain)
                line.unlink()
            except Exception as e:
                return data.update({"status": 400, "msg": e})
        else:
            data = {
                "status": 400,
                "data": None,
                "message": _("An already processed quotation can't be modified."),
            }
        return data
    

    @http.route(
            '/budget/update_pricelist', type="json", auth="public", website=False, sitemap=False
    )
    def update_pricelist(self, budget=False, fee=False, **kw):
        data = {"status": 200, "msg": _("Success")}
        
        if not budget:
            data.update(
                {"status": 204, "msg": _("No Found Budget"),  "data": False}
            )
            return json.dumps(data)
        
        try:
            sale_id = int(budget)
            sale_order = request.env["sale.order"].sudo().search([("id", "=", sale_id)])
            sale_order.update({
                "pricelist_id": int(fee)
            })
            sale_order.action_update_prices()
            sale = utils.browse_model_data("sale.order", sale_id)
            sale_json = sale.read(FIELDNAMES)
            if sale_json:
                sale_json = utils.convert_field_string(sale_json, PARSE_FIELDS)
                sale_json = utils.get_order_line(sale_json, FIELD_ORDER_LINE)
                data.update({"data": sale_json})

        except Exception as e:
            data.update({"status": 400, "msg": str(e)})
            return data

        return data

    @http.route(
            '/budget/update_partner', type="json", auth="public", website=False, sitemap=False
    )
    def update_partner(self, budget=False, partner=False, **kw):
        data = {"status": 200, "msg": _("Success")}
        
        if not budget or not partner:
            data.update(
                {"status": 204, "msg": _("No Found Budget or partner"),  "data": False}
            )
            return json.dumps(data)
        
        try:
            sale_id = int(budget)
            sale_order = request.env["sale.order"].sudo().search([("id", "=", sale_id)])
            sale_order.update({
                "partner_id": int(partner)
            })
        except Exception as e:
            data.update({"status": 400, "msg": str(e)})
            return data

        return data


    def check_lines_validations(self, lines):
        """Evaluates if the sale order lines have available quantities
        and the quantity meet the sales policy requirement.

        Parameters
        ----------
        lines
            Sale Order Lines to evaluate.

        Returns
        -------
            a tuple containing True and an empty string if everything is ok,
            False and a message if any of the validations were turned on.
        """

        for line in lines:
            product_id = int(line.get("product_id"))
            product = utils.browse_model_data("product.product", product_id)

            warehouse_id = int(utils.get_config("main_warehouse_id"))

            warehouse = utils.browse_model_data("stock.warehouse", warehouse_id)

            if not warehouse:
                message = _("There's no main warehouse assigned")
                return False, message
            if warehouse:
                product = product.with_context(warehouse=warehouse.id)

            if product and product.free_qty < int(line.get("product_uom_qty")):
                message = _(
                    "The product '%(product_name)s' quantity exceed the availability (%(product_quantity).2f)"
                ) % {
                    "product_name": product.display_name,
                    "product_quantity": product.free_qty,
                }
                return False, message
            # if (
            #     product
            #     # and product.sales_policy > 1
            #     # and product.available_qty >= product.sales_policy
            #     # and int(line.get("product_uom_qty")) % product.sales_policy != 0
            # ):
            #     message = _(
            #         "The product %(product_name)s have a sales policy, the quantity you want to sale must be a multiple or equal to %(product_policy)d"
            #     ) % {"product_name": product.display_name, "product_policy": product.sales_policy}
            #     False, message

        return True, ""

    def check_lines_validations_order(self, lines):
        """Evaluates if the sale order lines have available quantities
        and the quantity meet the sales policy requirement.

        Parameters
        ----------
        lines
            Sale Order Lines to evaluate.

        Returns
        -------
            a tuple containing True and an empty string if everything is ok,
            False and a message if any of the validations were turned on.
        """

        for line in lines:
            product = line.product_id
            success, msg = self._confirm_check_availability_sale(line)
            if not success:
                return False, msg
            # if (
            #     product
            #     # and product.sales_policy > 1
            #     # and product.available_qty >= product.sales_policy
            #     # and line.product_uom_qty % product.sales_policy != 0
            # ):
            #     message = _(
            #         "The product %(product_name)s have a sales policy, the quantity you want to sale must be a multiple or equal to %(product_policy)d"
            #     ) % {"product_name": product.display_name, "product_policy": product.sales_policy}
            #     return False, message

        return True, ""

    def _confirm_check_availability_sale(self, line):
        """Evaluates if there availability on a given sale order line

        Parameters
        ----------
        line
            The sale order line you want to evaluate availability

        Returns
        -------
            True and an empty string if everything is ok, False and a message
            otherwise.
        """

        if line.product_id.type == "product" and line.warehouse_id:
            warehouse_id = line.warehouse_id.id
            lang = line.order_id.partner_id.lang or request.env.user.lang or "es_VE"
            product = line.product_id.with_context(warehouse=warehouse_id, lang=lang)
            allow_out_of_stock_order = request.env['res.config.settings'].sudo().get_values().get('allow_out_of_stock_order')  # Crear una instancia temporal de res.config.settings

            if product.free_qty < line.product_uom_qty and not allow_out_of_stock_order:
                message = _(
                    "Estás tratando de vender %(uom_qty).2f %(uom)s de %(product_name)s Pero solo tienes %(product_quantity).2f %(uom)s disponible en %(warehouse)s."
                ) % {
                    "uom_qty": line.product_uom_qty,
                    "uom": line.product_id.uom_id.name,
                    "product_name": line.product_id.display_name,
                    "product_quantity": product.free_qty,
                    "warehouse": line.warehouse_id.name,
                }
                return False, message

        return True, ""

    def include_product_tax(self, order_lines):
        new_order_lines = []
        for line in order_lines:
            line_cpy = line.copy()
            product_id = int(line.get("product_id")[0])
            product_tax = utils.browse_model_data("product.product", product_id).taxes_id[0].id
            line_cpy["tax_id"] = [
                product_tax,
            ]
            new_order_lines.append(line_cpy)

        return new_order_lines
