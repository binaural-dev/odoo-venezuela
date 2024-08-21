from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

POLICY_TYPE = {"1_product": _("Producto"), "2_brand": _("Marca"), "3_category": _("Categoria")}

import logging

_logger = logging.getLogger(__name__)


class CommissionPolicyItem(models.Model):
    _name = "commission.product.item"
    _description = "Commission Product Item"
    _order = "applied_on asc"

    product_id = fields.Many2one("product.product", string="Product")
    brand_id = fields.Many2one("product.brand", string="Brand")
    category_id = fields.Many2one("product.category", string="Category", store=True)
    name = fields.Char(string="Name", compute="_compute_name")
    applied_on = fields.Selection(
        selection=[("1_product", "Product"), ("2_brand", "Brand"), ("3_category", "Category")],
        default="1_product",
        string="Applied On",
        required=True,
    )
    excluded = fields.Boolean("Excluded")
    commission_policy_id = fields.Many2one("commission.policy", string="Commission Policy")
    len_category_sub_category = fields.Integer(
        compute="_compute_len_category_sub_category", store=True
    )

    def show_products_brands(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Products",
            "res_model": "product.product",
            "view_mode": "tree",
            "domain": [("brand_id", "=", self.brand_id.id), ("commission_item_ids", "=", False)],
            "target": "new",
        }

    def show_products_categories(self):
        category_ids = self.category_id.ids
        categories = self.category_id
        finish_categ = False
        while not finish_categ:
            if len(categories.child_id.ids) == 0:
                finish_categ = True

            category_ids += categories.child_id.ids
            categories = categories.child_id

        return {
            "type": "ir.actions.act_window",
            "name": "Products",
            "res_model": "product.product",
            "view_mode": "tree",
            "domain": [("categ_id", "in", category_ids), ("commission_item_ids", "=", False)],
            "target": "new",
        }

    @api.depends("category_id", "len_category_sub_category")
    def _compute_len_category_sub_category(self):
        for record in self:
            if not record.category_id:
                record.len_category_sub_category = 0
                continue
            text = record.category_id.complete_name
            record.len_category_sub_category = len(text.split("/"))

    @api.depends("product_id", "applied_on")
    def _compute_name(self):
        for record in self:
            if not record.product_id and record.applied_on == "1_product":
                record.name = ""
                continue
            if record.applied_on == "1_product":
                text = POLICY_TYPE.get(record.applied_on, "")
                text += ": " + record.product_id.name
                if record.excluded:
                    text += " (Excluido)"
                record.name = text
            if record.applied_on == "2_brand":
                record.name = f"{POLICY_TYPE.get(record.applied_on,'')}: {record.brand_id.name}"
            if record.applied_on == "3_category":
                record.name = f"{POLICY_TYPE.get(record.applied_on,'')}: {record.category_id.name}"

    @api.onchange("applied_on")
    def _onchange_applied_on(self):
        self.product_id = False
        self.brand_id = False
        self.category_id = False

    @api.constrains("product_id")
    def _constraint_product_id(self):
        for record in self:
            if not record.product_id:
                continue
            exist = self.search(
                [("product_id", "=", record.product_id.id), ("id", "!=", record.id)]
            )

            if any(exist):
                raise ValidationError(
                    _(
                        "%s This product already belongs to another product policy",
                        record.product_id.name,
                    )
                )

    @api.constrains("brand_id")
    def _constraint_brand_id(self):
        for record in self:
            if not record.brand_id:
                continue
            exist = self.search([("brand_id", "=", record.brand_id.id), ("id", "!=", record.id)])

            if any(exist):
                raise ValidationError(
                    _(
                        "%s This brand already belongs to another brand policy",
                        record.brand_id.name,
                    )
                )

    @api.constrains("category_id")
    def _constraint_category_id(self):
        for record in self:
            if not record.category_id:
                continue
            exist = self.search(
                [("category_id", "=", record.category_id.id), ("id", "!=", record.id)]
            )

            if any(exist):
                raise ValidationError(
                    _(
                        "%s This category already belongs to another category policy",
                        record.category_id.name,
                    )
                )

    @api.model
    def _get_commission_product_items(self, lines):
        model_name = lines._name
        lines_with_commission = self.env[model_name]
        line_comission = []

        product_ids = lines.product_id
        brand_ids = product_ids.brand_id.ids
        category_ids = product_ids.categ_id.ids
        categories = product_ids.categ_id
        finish_categ = False
        while not finish_categ:
            if len(categories.parent_id.ids) == 0:
                finish_categ = True

            category_ids += categories.parent_id.ids
            categories = categories.parent_id

        CommisionPolicesItem = self.env["commission.product.item"]
        items = CommisionPolicesItem.search(
            [("product_id", "in", product_ids.ids), ("applied_on", "=", "1_product")]
        )
        if len(brand_ids) > 0:
            items += CommisionPolicesItem.search(
                [("brand_id", "in", brand_ids), ("applied_on", "=", "2_brand")]
            )
        if len(category_ids) > 0:
            items += CommisionPolicesItem.search(
                [
                    ("category_id", "in", category_ids),
                    ("applied_on", "=", "3_category"),
                ],
                order="len_category_sub_category desc",
            )

        processed_lines = []
        for item in items:
            for line in lines:
                if line.id in processed_lines:
                    continue
                if line.product_id == item.product_id:
                    if item.excluded:
                        processed_lines.append(line.id)
                        continue
                    line_comission.append((line, item))
                    processed_lines.append(line.id)
                    lines_with_commission |= line
                    continue

                if item.brand_id and line.product_id.brand_id == item.brand_id:
                    line_comission.append((line, item))
                    processed_lines.append(line.id)
                    lines_with_commission |= line
                    continue

                if not item.category_id or not line.product_id.categ_id:
                    continue

                category = line.product_id.categ_id
                finish = False
                while not finish:
                    if category == item.category_id:
                        line_comission.append((line, item))
                        processed_lines.append(line.id)
                        lines_with_commission |= line
                        finish = True
                    elif not category.parent_id:
                        finish = True
                    else:
                        category = category.parent_id

        return lines_with_commission, line_comission

