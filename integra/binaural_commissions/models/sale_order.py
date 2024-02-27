import json
from odoo import api, models, fields
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)

    @api.model
    def fields_to_read_from_commission_policy_line(self):
        return [
            "date_from",
            "date_to",
            "commission",
            "percentage_report",
            "not_applied",
            "policy_type",
        ]

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
        Create and assign commission policy line images to order lines depending on the commission
        policy of the product of each line and the client of the order.

        The priority for assigning commission policy line images for each line is:
            1. Commission policy of the product of the line.
            2. Commission policy of the client of the order.
            3. Commission of type "all".

        This means that if a product has a commission policy assigned, the commission policy of the
        client of the order will be ignored for that product. If the product does not have a
        commission policy assigned, the commission policy of the client of the order will be
        assigned to the line. If the product and the client of the order do not have a commission
        policy assigned, the commission policy of type "all" will be assigned to the line.

        The commission policy line images are created from the commission policy lines of the
        corresponding commission policy. The commission policy line images are created only once
        for each commission policy and are assigned to all the lines to which that commission policy
        applies.

        This method is called when the order is confirmed, so the commission policy line images are
        assigned to the order lines only once.

        TODO: We have to think what to do when the order is cancelled. (Maybe we should delete the
        commission policy line images of the order lines in that case.)

        Returns
        -------
        None
        """
        CommissionPolicy = self.env["commission.policy"]
        CommissionPolicyLineImage = self.env["commission.policy.line.image"]

        (
            lines_with_commissions_type_product,
            lines_commissions,
        ) = self._get_commission_product_items(self.order_line)

        fields_to_read_from_commission_policy_line = (
            self.fields_to_read_from_commission_policy_line()
        )

        policy_line_images_grouped_by_commission_policy = defaultdict(
            lambda: self.env["sale.order.line"]
        )

        lines_with_commissions_types_other_than_product = (
            self.order_line - lines_with_commissions_type_product
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
            commission_policy_lines = commission_policy_id.commission_line_ids.read(
                fields_to_read_from_commission_policy_line
            )
            images = CommissionPolicyLineImage.create(commission_policy_lines)
            line.commission_policy_line_image_ids = images.ids
            policy_line_images_grouped_by_commission_policy[commission_policy_id] = images

        client_policies = CommissionPolicy.search([("policy_type", "=", "client")])

        for policy in client_policies:
            if self.partner_id in policy.clients_id:
                images = CommissionPolicyLineImage.create(
                    policy.commission_line_ids.read(fields_to_read_from_commission_policy_line)
                )
                lines_with_commissions_types_other_than_product.write(
                    {"commission_policy_line_image_ids": [(4, image.id) for image in images]}
                )
                return
        all_policy = CommissionPolicy.search([("policy_type", "=", "all")], limit=1)
        images = CommissionPolicyLineImage.create(
            all_policy.commission_line_ids.read(fields_to_read_from_commission_policy_line)
        )
        lines_with_commissions_types_other_than_product.write(
            {"commission_policy_line_image_ids": [(4, image.id) for image in images]}
        )
        return

    def set_company_settings(self):
        self.commission_invoice_date_field = self.company_id.commission_invoice_date_field
        self.compute_commission_when = self.company_id.compute_commission_when

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
        return res

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            order.assing_commission_policy_line_images_to_order_lines()
            order.set_company_settings()
        return res
