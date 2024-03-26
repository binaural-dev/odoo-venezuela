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

    @api.model
    def _get_products_domain(self):
        commission_product_ids = self.get_commission_product_ids("product", ["brand", "category"])
        return [("id", "not in", commission_product_ids)]

    name = fields.Char(required=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    policy_type = fields.Selection(
        selection=[("product", "Product"), ("client", "Client"), ("all", "General")],
        string="Commission Type",
        required=True,
    )
    clients_id = fields.Many2many("res.partner", "commission_policy_client_rel", string="Clients")
    commission_line_ids = fields.One2many("commission.policy.line", "policy_id")
    commission_product_item_ids = fields.One2many("commission.product.item", "commission_policy_id")

    @api.onchange("policy_type")
    def _onchange_policy_type(self):
        if self.clients_id:
            raise ValidationError(_("You can't change the policy type if there are clients assigned"))
        if self.commission_product_item_ids:
            raise ValidationError(_("You can't change the policy type if there are products assigned"))

    def unlink(self):
        for record in self:
            unlink(record.commission_product_item_ids.ids)
        return super().unlink()

    @api.depends("policy_type", "name")
    def _compute_display_name(self):
        for commission in self:
            policy_type = dict(self._fields["policy_type"]._description_selection(self.env)).get(
                commission.policy_type
            )
            commission.display_name = f"{policy_type}" f" ({commission.name})"

    def create_image_lines(self):
        commission_lines = self.commission_line_ids
        read_lines = commission_lines.read(["date_from", "date_to", "commission", "policy_type"])
        res = [(0, 0, line) for line in read_lines]
        return res
