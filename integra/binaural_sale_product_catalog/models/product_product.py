from odoo import models, fields, _


class Product(models.Model):
    _inherit = "product.product"

    _quantity = fields.Integer(default=0, store=True)

    def open_product_edit(self):
        form_view = self.env.ref("product.product_normal_form_view")
        return {
            "type": "ir.actions.act_window",
            "name": _("Edit Product"),
            "res_model": "product.product",
            "res_id": self.id,
            "views": [(form_view.id, "form")],
            "target": "self",
        }

    def sale_order_line_item(self):
        return {
            "product_id": self.id,
            "price_unit": self.list_price,
            "product_uom": self.uom_id.id,
        }

    def _get_add_products_to_sol(self, sale_id):
        sol_ = self.env["sale.order.line"]
        exitsts_products_ids = sol_.search(
            [("order_id", "=", sale_id), ("product_id", "in", self.ids)]
        )
        exitsts_products_ids = exitsts_products_ids.mapped("product_id")
        exitsts_products_ids = exitsts_products_ids.ids
        _add_products_ids = self.filtered(
            lambda record: record.id not in exitsts_products_ids
        )
        return _add_products_ids

    def sale_order_line_create(self):
        """
        Create Sale Order Lines By Or Edit
        Selected Product Or Products
        """

        context = self.env.context.copy() or {}
        sale_id = {"sale_id": context.get("sale_id")} or None
        product_ids = self._get_add_products_to_sol(sale_id.get("sale_id"))

        so_lines = []

        for product in product_ids:
            get_so_line_ = product.sale_order_line_item()
            get_so_line_["order_id"] = sale_id.get("sale_id")
            so_lines.append(get_so_line_)
        self.env["sale.order.line"].create(so_lines)

    def utilizable_cart_details(self):
        """
        Utilizable Cart Details For Remove ,
        Add And Update Operations
        """

        context = self._context.copy() or {}
        cart_object = self.env["sale.order.line"]
        cart_details = dict()
        total_count = cart_object.search_count(
            [("product_id", "=", self.id), ("order_id", "=", context.get("sale_id"))]
        )
        cart_details["total_count"] = total_count
        cart_data = cart_object.search(
            [("product_id", "=", self.id), ("order_id", "=", context.get("sale_id"))]
        )
        cart_details["cart_data"] = cart_data
        return cart_details

    def initiate_sol(self, operation, sale_id):
        """
        Initiate Sale Order Line By Cart Functionality.
        """

        so_object = self.env["sale.order"]
        sale_object = so_object.search([("id", "=", sale_id)])
        if operation == "add":
            so_object.sol_by_cart(operation, self, sale_object)
        elif operation == "remove":
            so_object.sol_by_cart(operation, self, sale_object)
        elif operation == "update":
            so_object.sol_by_cart(operation, self, sale_object)

    def set_quantity(self, quantity, operation=None):
        context = self._context.copy() or {}
        cart_details = self.utilizable_cart_details()
        if operation == "remove":
            self._quantity -= quantity
            if cart_details.get("total_count") != 0:
                self.initiate_sol("remove", context.get("sale_id"))
        else:
            self._quantity += quantity
            if cart_details.get("total_count") != 0:
                self.initiate_sol("update", context.get("sale_id"))
            else:
                self.initiate_sol("add", context.get("sale_id"))

        if self._quantity == 0:
            if cart_details.get("total_count") != 0:
                cart_data = cart_details.get("cart_data")
                cart_data.unlink()

    def remove_quantity_button(self):
        if self._quantity == 0:
            self._quantity = 0
            return
        return self.set_quantity(1, operation="remove")

    def add_quantity_button(self):
        return self.set_quantity(1, operation="add")
