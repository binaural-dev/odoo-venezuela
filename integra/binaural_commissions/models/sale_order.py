import json
from odoo import models, fields
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    commission_invoice_date_field = fields.Char(readonly=True,copy=False)
    compute_commission_when = fields.Char(readonly=True,copy=False)

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
        product_policies = CommissionPolicy.search([("policy_type", "=", "product")])
        fields_to_read_from_commission_policy_line = [
            "date_from",
            "date_to",
            "commission",
            "percentage_report",
            "not_applied",
        ]
        policy_line_images_grouped_by_commission_policy = defaultdict(
            lambda: self.env["sale.order.line"]
        )
        lines_with_commissions_types_other_than_product = self.order_line

        for product in product_policies.product_ids:
            lines_with_product_on_commission_policies = self.order_line.filtered(
                lambda l: l.product_id == product
            )
            lines_with_commissions_types_other_than_product -= (
                lines_with_product_on_commission_policies
            )
            for line in lines_with_product_on_commission_policies:
                commission_policy_id = product.commission_policy_id
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
