import logging
from os import unlink
from typing import List, Union
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
            unlink(record.commission_product_item_ids.ids)
        return super().unlink()

    @api.depends("policy_type", "name")
    def _compute_display_name(self):
        for commission in self:
            commission.display_name = f"{commission.policy_type_id.name}" f" ({commission.name})"

    def available_to_policy_type_and_create_image(self, lines):
        CommissionPolicyLineImage = self.env["commission.policy.line.image"]
        if not lines:
            return self.env["sale.order.line"]

        lines_applied = self.env["sale.order.line"]

        for record in self:
            if record.policy_type == "client":
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

            if record.policy_type == "pricelist":
                # CASE CLIENT
                for pricelist_id in lines.order_id.pricelist_id:
                    pricelist_lines = lines.filtered(lambda x: x.order_id.pricelist_id.id == pricelist_id.id)
                    if pricelist_id in record.pricelist_id:
                        images = CommissionPolicyLineImage.create(
                            record.commission_line_ids._prepare_commission_line_image()
                        )
                        lines_applied += pricelist_lines
                        pricelist_lines.write(
                            {"commission_policy_line_image_ids": [(4, image.id) for image in images]}
                        )
                return lines_applied

            if record.policy_type == "all":
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
