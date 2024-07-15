import logging
from os import unlink
from typing import List, Union
from collections import defaultdict
import traceback

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class CommissionPolicy(models.Model):
    _name = "commission.policy"
    _description = "commission policy for sellers"
    _order = "sequence asc"

    @api.model
    def _get_products_domain(self):
        commission_product_ids = self.get_commission_product_ids("product", ["brand", "category"])
        return [("id", "not in", commission_product_ids)]

    name = fields.Char(required=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    policy_type_id = fields.Many2one("commission.policy.type")
    policy_type_name = fields.Selection(related="policy_type_id.policy_type")
    sequence = fields.Integer(related="policy_type_id.sequence", store=True)
    policy_type = fields.Selection(
        selection=[("product", "Product"), ("client", "Client"), ("all", "General")],
        default="all",
        string="Commission Type",
        required=True,
    )
    pricelist_ids  = fields.Many2many("product.pricelist", string="Pricelists")
    clients_id = fields.Many2many("res.partner", "commission_policy_client_rel", string="Clients")
    commission_line_ids = fields.One2many("commission.policy.line", "policy_id")
    commission_product_item_ids = fields.One2many("commission.product.item", "commission_policy_id")
    text_priority = fields.Text(compute="_compute_text_priority")

    @api.depends("text_priority")
    def _compute_text_priority(self):
        policies = self.env["commission.policy.type"].search([])
        text = _("""Policy Type Priority:\n""")
        for policy in policies:
            text += _("- %s (Priority %s)\n" % (policy.name, policy.sequence))

        for record in self:
            record.text_priority = text

    @api.onchange("policy_type_id")
    def _onchange_policy_type_id(self):
        if self.clients_id:
            raise ValidationError(_("You can't change the policy type if there are clients assigned"))
        if self.pricelist_ids:
            raise ValidationError(_("You can't change the policy type if there are pricelists assigned"))
        if self.commission_product_item_ids:
            raise ValidationError(_("You can't change the policy type if there are products assigned"))

    def unlink(self):
        for record in self:
            record.commission_product_item_ids.unlink()
        return super().unlink()

    @api.depends("policy_type_name", "name")
    def _compute_display_name(self):
        for commission in self:
            commission.display_name = f"{commission.policy_type_id.name}" f" ({commission.name})"

    def available_to_policy_type_and_create_image(self, lines):
        model_name = lines._name
        CommissionPolicyLineImage = self.env["commission.policy.line.image"]
        if not lines:
            return self.env[model_name]

        lines_applied = self.env[model_name]

        for record in self:
            if record.policy_type_name == "client":
                # CASE CLIENT
                for partner in lines.order_id.partner_id:
                    partner_lines = lines.filtered(lambda x: x.order_id.partner_id.id == partner.id)
                    if partner in record.clients_id:
                        images = CommissionPolicyLineImage.create(
                            record.commission_line_ids._prepare_commission_line_image()
                        )
                        lines_applied += partner_lines
                        partner_lines.write(
                            {"commission_policy_line_image_ids": [(4, image.id) for image in images]}
                        )
                return lines_applied

            if record.policy_type_name == "pricelist":
                # CASE PRICELIST
                for pricelist_id in lines.pricelist_item_id.pricelist_id:
                    pricelist_lines = lines.filtered(lambda x: x.pricelist_item_id.pricelist_id.id == pricelist_id.id)
                    if pricelist_id in record.pricelist_ids:
                        images = CommissionPolicyLineImage.create(
                            record.commission_line_ids._prepare_commission_line_image()
                        )
                        lines_applied += pricelist_lines
                        pricelist_lines.write(
                            {"commission_policy_line_image_ids": [(4, image.id) for image in images]}
                        )
                return lines_applied

            if record.policy_type_name == "all":
                images = CommissionPolicyLineImage.create(
                    record.commission_line_ids._prepare_commission_line_image()
                )
                lines_applied += lines
                lines.write(
                    {"commission_policy_line_image_ids": [(4, image.id) for image in images]}
                )
                return lines_applied

    def create_image_lines(self):
        commission_lines = self.commission_line_ids
        read_lines = commission_lines.read(["date_from", "date_to", "commission", "policy_type"])
        res = [(0, 0, line) for line in read_lines]
        return res

    def assing_commission_policy_line_images_to_lines(self, lines):
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
        model_name = lines._name
        CommissionPolicy = self.env["commission.policy"]
        CommissionPolicyLineImage = self.env["commission.policy.line.image"]
        CommisionPolicesItem = self.env["commission.product.item"]

        (
            lines_with_commissions_type_product,
            lines_commissions,
        ) = CommisionPolicesItem._get_commission_product_items(lines)

        policy_line_images_grouped_by_commission_policy = defaultdict(
            lambda: self.env[model_name]
        )

        lines_without_commissions_type_product = (
            lines - lines_with_commissions_type_product
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
