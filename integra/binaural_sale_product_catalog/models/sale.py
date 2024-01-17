from odoo import models, fields, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def product_catelog(self):
        cart_object = self.env["sale.order.line"]
        product_object = self.env["product.product"]
        cart_products_details = cart_object.search([("order_id", "=", self.id)])
        if len(cart_products_details) > 0:
            for rec in cart_products_details:
                assign_quantity = rec.product_uom_qty
                rec.product_id._quantity = assign_quantity
        else:
            product_object_data = product_object.search([("_quantity", "!=", 0)])
            for rec in product_object_data:
                rec._quantity = 0

        kanban_view = self.env.ref(
            "binaural_sale_product_catalog.product_product_view_kanban_product_catalogue"
        )
        tree_view = self.env.ref(
            "binaural_sale_product_catalog.product_product_view_tree_product_catalogue"
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Choose Products"),
            "res_model": "product.product",
            "domain": [("quantity", ">", 0)],
            "views": [(kanban_view.id, "kanban"), (tree_view.id, "tree")],
            "context": {"_quantity_change": True, "sale_id": self.id, "create": 0},
            "help": _(
                """<p class="o_view_nocontent_smiling_face">
                            Create a new product
                        </p>"""
            ),
        }

    def sol_by_cart(self, operation, product_id, sale_id):
        """
        Create Sale Order Line By
        Cart Functionality
        """

        sol_object = self.env["sale.order.line"]

        sol_data = dict()
        sol_data["product_id"] = product_id.id
        sol_data["order_id"] = sale_id.id
        sol_data["price_unit"] = product_id.lst_price
        sol_data["product_uom"] = product_id.uom_id.id
        sol_data["name"] = product_id.name
        if operation == "add":
            sol_data["product_uom_qty"] = product_id._quantity
            sol_object.create(sol_data)
            return

        sol_ = sol_object.search(
            [("order_id", "=", sale_id.id), ("product_id", "=", product_id.id)]
        )

        if operation == "remove":
            if product_id._quantity == 0:
                sol_.unlink()
                return
            sol_["product_uom_qty"] = product_id._quantity

        elif operation == "update":
            sol_["product_uom_qty"] = product_id._quantity
        return

    def user_input_qty_sol(
        self, _qty, product_id, sale_id, name, customer_lead, list_price
    ):
        sale_object = self.env["sale.order"].browse(sale_id)
        sol_object = self.env["sale.order.line"].with_company(sale_object.company_id.id)
        product_object = self.env["product.product"].with_company(
            sale_object.company_id.id
        )
        cart_product_details = sol_object.search(
            [("order_id", "=", sale_id), ("product_id", "=", product_id)]
        )

        if len(cart_product_details) > 0:
            if _qty == 0:
                product_id._quantity = 0
                cart_product_details.unlink()
                return
            cart_product_details.product_uom_qty = _qty
            return
        else:
            sol_data = dict()
            sol_data["product_id"] = product_id
            sol_data["order_id"] = sale_id
            sol_data["name"] = name
            sol_data["price_unit"] = list_price
            sol_data["product_uom"] = "1"
            sol_data["product_uom_qty"] = _qty
            sol_data["customer_lead"] = customer_lead
            sol_object.sudo().create(sol_data)
            return
