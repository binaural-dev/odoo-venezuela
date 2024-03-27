import json
from odoo import api, models, fields, _
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)
    priority_commission_policy_type = fields.Char(readonly=True, copy=False)

    @api.model
    def _get_commission_product_items(self, lines):
        lines_with_commission = self.env["sale.order.line"]
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
        if len(brand_ids) > 1:
            items += CommisionPolicesItem.search(
                [("brand_id", "in", brand_ids), ("applied_on", "=", "2_brand")]
            )
        if len(category_ids) > 1:
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

    def assing_commission_policy_line_images_to_order_lines(self):
        """
        This function assigns the commissions available for the lines.

        Generating an exact copy of the commission lines so that when the invoice is
        created they can be calculated.

        Depending on the configuration, the order will depend.

        1. Product
        2. XXX
        3. XXX
        4. XXX
        5. General
        """
        CommissionPolicy = self.env["commission.policy"]
        CommissionPolicyLineImage = self.env["commission.policy.line.image"]

        lines_without_notes = self.order_line.filtered(lambda x: not x.display_type)

        (
            lines_with_commissions_type_product,
            lines_commissions,
        ) = self._get_commission_product_items(lines_without_notes)

        policy_line_images_grouped_by_commission_policy = defaultdict(
            lambda: self.env["sale.order.line"]
        )

        lines_without_commissions_type_product = (
            lines_without_notes - lines_with_commissions_type_product
        )

        for line_commission in lines_commissions:
            line = line_commission[0]
            commission_item = line_commission[1]

            commission_policy_id = commission_item.commission_policy_id

            if commission_policy_id in policy_line_images_grouped_by_commission_policy:
                line.commission_policy_line_image_ids = (
                    policy_line_images_grouped_by_commission_policy[commission_policy_id]
                )
                continue

            commission_policy_lines = (
                commission_policy_id.commission_line_ids._prepare_commission_line_image()
            )
            images = CommissionPolicyLineImage.create(commission_policy_lines)
            line.commission_policy_line_image_ids = images.ids
            policy_line_images_grouped_by_commission_policy[commission_policy_id] = images

        policies = CommissionPolicy.search([("policy_type_id.policy_type", "!=", "product")])

        for policy in policies:
            lines_without_commissions_type_product -= (
                policy.available_to_policy_type_and_create_image(
                    lines_without_commissions_type_product
                )
            )

        return

    def set_company_settings(self):
        self.commission_invoice_date_field = self.company_id.commission_invoice_date_field
        self.compute_commission_when = self.company_id.compute_commission_when
        self.priority_commission_policy_type = (
            "/".join(self.env["commission.policy.type"].search([]).mapped("name"))
        )

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        res = super()._prepare_invoice()
        res["commission_invoice_date_field"] = self.commission_invoice_date_field
        res["compute_commission_when"] = self.compute_commission_when
        res["priority_commission_policy_type"] = self.priority_commission_policy_type
        return res

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            order.assing_commission_policy_line_images_to_order_lines()
            order.set_company_settings()
        return res

    def set_commission_from_sale(self):
        view = self.env.ref("binaural_commissions.set_commission_order_to_invoice_form")
        return {
            "name": _("Set Commission Order to Invoice"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "set.commission.order.to.invoice",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "flags": {"mode": "readonly"},
            "context": dict(
                self.env.context,
                default_sale_order_ids=self.ids,
            ),
        }
