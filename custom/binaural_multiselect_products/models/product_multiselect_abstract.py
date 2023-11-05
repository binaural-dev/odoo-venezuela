from random import randint
from odoo import models, _
import logging

_logger = logging.getLogger(__name__)


class ProductMultiselectAbstract(models.AbstractModel):
    _name = "product.multiselect.abstract"

    def display_select_product_view(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Multi Product Selector"),
            "view_mode": "tree",
            "res_model": "product.product",
            "target": "new",
            # 'res_id': new_wizard.id,
            # 'views': [[view_id, 'form']],
            "context": {
                "default_is_trigger_from_multiselect": True,
                "default_record_id": self.env.context.get("default_record_id", None),
                "default_model_for_multiselect": self.env.context.get(
                    "default_model_for_multiselect", None
                ),
                "default_model_line": self.env.context.get(
                    "default_model_line", None
                ),
                "default_field_line_related": self.env.context.get(
                    "default_field_line_related", None
                )
            },
        }

    # Executed on product.product model on click action button
    def create_order_line(self, product_id):
        product = self.env["product.product"].browse([product_id])

        return {
            "name": product.name,
            "order_id": self.id,
            "product_id": product.id,
            "product_uom": product.uom_id.id,
        }
        
    
    def is_invalid_create_order_line(self, selected_product_id):
        if selected_product_id in self.order_line.mapped('product_id.id'):
            return True
        
        return False
        

    # Executed on product.product model on click action button
    def set_new_order_lines(self, selected_product_ids, model_line, field_line_related):
        order_line_model = self.env[model_line]
        new_order_line_ids = []

        for selected_product_id in selected_product_ids:
            
            if self.is_invalid_create_order_line(selected_product_id):
                continue
            
            order_line_prepare = self.create_order_line(selected_product_id)

            new_order_line = order_line_model.create(order_line_prepare)
            new_order_line_ids.append(new_order_line.id)

        order_line_ids =  [
            *self.order_line.ids,
            *new_order_line_ids
        ]

        order_lines = self.env[model_line].browse(order_line_ids)

        self.update({
            field_line_related: order_lines
        })
