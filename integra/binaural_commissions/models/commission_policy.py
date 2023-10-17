import logging
from typing import List, Union

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
        selection=[("client", "Client"), ("product", "Product"), ("all", "General")],
        string="Commission Type",
        required=True,
    )
    product_commission_type = fields.Selection(
        selection=[("product", "Product"), ("category", "Category"), ("brand", "brand")],
        string="Apply To",
    )
    is_report_range = fields.Boolean(groups="base.group_no_one", copy=False)
    clients_id = fields.Many2many("res.partner", "commission_policy_client_rel", string="Clients")
    products_id = fields.Many2many(
        "product.product",
        "commission_policy_product_rel",
        domain=_get_products_domain,
    )
    brands_id = fields.Many2many("product.brand", "commission_policy_brand_rel")
    categories_id = fields.Many2many("product.category", "commission_policy_category_rel")
    commission_line_ids = fields.One2many("commission.policy.line", "policy_id")
    product_ids = fields.One2many("product.product", "commission_policy_id")

    @api.depends("policy_type", "name")
    def _compute_display_name(self):
        for commission in self:
            policy_type = dict(self._fields["policy_type"]._description_selection(self.env)).get(
                commission.policy_type
            )
            commission.display_name = f"{policy_type}" f" ({commission.name})"

    @api.constrains("commission_line_ids")
    def _check_previous_range_date_to(self):
        for commission in self:
            if len(commission.commission_line_ids) > 1:
                commission_lines_list = sorted(
                    commission.commission_line_ids, key=lambda x: x.date_from
                )
                if commission_lines_list[-1].date_from <= commission_lines_list[-2].date_to:
                    raise ValidationError(
                        _(
                            "The commission date from must be lower or equal to the "
                            "latest commission date to."
                        )
                    )

    @api.onchange("policy_type")
    def _onchange_product_policy_type(self):
        if self.policy_type != "product":
            self.product_commission_type = False

    @api.onchange("products_id")
    def onchange_update_product_domain(self):
        domain = self._get_products_domain()
        return {"domain": {"products_id": domain}}

    @api.onchange("product_commission_type")
    def _onchange_product_commission_type(self):
        for commission in self:
            if commission.product_commission_type == "product":
                commission.brands_id = False
                commission.categories_id = False
            if commission.product_commission_type == "category":
                commission.products_id = False
                commission.brands_id = False
            if commission.product_commission_type == "brand":
                commission.products_id = False
                commission.categories_id = False

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for commission in res:
            if commission.categories_id or commission.brands_id:
                sub_category = commission.product_commission_type
                categ_brand_ids = commission.categories_id.ids or commission.brands_id.ids
                product_ids = commission.get_products_based_in_product_sub_category(
                    sub_category, tuple(categ_brand_ids)
                )
                commission.product_ids = product_ids

        return res

    def write(self, vals):
        if vals.get("product_ids", False):
            product_ids = vals.get("product_ids")
            if not all([isinstance(item, int) for item in product_ids]):
                new_product_ids = list(map(lambda x: [3] + x[1:] if x[0] == 2 else x, product_ids))
                vals.update({"product_ids": new_product_ids})

        res = super().write(vals)
        if vals.get("categories_id", False) or vals.get("brands_id", False):
            sub_category = self.product_commission_type
            categ_brand_ids = self.categories_id.ids or self.brands_id.ids
            product_ids = self.get_products_based_in_product_sub_category(
                sub_category, tuple(categ_brand_ids)
            )
            self.product_ids = product_ids

        return res

    @api.model
    def get_products_based_in_product_sub_category(
        self, sub_category: str, categ_brand_ids: tuple
    ) -> list:
        self.ensure_one()

        product = self.env["product.product"]
        products_ids = tuple(self.get_commission_product_ids("product", ["product"]))
        domain = [("id", "not in", products_ids)]

        if not sub_category:
            return []

        if sub_category == "category":
            domain = expression.AND([domain, [("categ_id", "in", categ_brand_ids)]])
        if sub_category == "brand":
            domain = expression.AND([domain, [("brand_id", "in", categ_brand_ids)]])

        res = product.search(domain).ids
        return res

    @api.model
    def get_commission_product_ids(self, policy_type: str, product_policy_types=None) -> List[int]:
        if product_policy_types is None:
            product_policy_types = []

        commission_product_ids = set()
        commissions = self.get_commission(policy_type, product_policy_types)

        for commission in commissions:
            if commission.product_commission_type == "product":
                commission_product_ids.update(commission.products_id.ids)
            else:
                commission_product_ids.update(commission.product_ids.ids)

        return list(commission_product_ids)

    @api.model
    def get_commission(self, policy_type: str, product_policy_types: Union[str, List[str]] = False):
        """
        Method to get the commission policy wich will be applied to a given product

        :param policy_type: The type of commission policy.
        :param product_policy_types: The types of products policies.
        :return: recordset of  a commission policy found in given types.
        """
        commission_policy = None
        domain = [("policy_type", "=", policy_type)]

        if isinstance(product_policy_types, (str, bool)):
            domain = expression.AND(
                [domain, [("product_commission_type", "=", product_policy_types)]]
            )
        else:
            domain = expression.AND(
                [domain, [("product_commission_type", "in", product_policy_types)]]
            )

        commission_policy = self.search(domain)
        return commission_policy

    @api.model
    def get_or_create_commission_image(
        self, picking_ids, policy_type, product_commission_type=False
    ):
        """
        Method to create a commission image if the current commission policy has
        been modified or to get the image with the picking reference to link which
        commission will be applied.

        :param picking_ids: The pickings which will be set in the commission image.
        :param policy_type: The type of commission policy.
        :param product_commission_type: The type of product policy.
        :return: a recordset with a new commission image or the current one.
        """
        commission_image = self.env["commission.policy.image"]
        commission_i = commission_image.get_image_commission(policy_type, product_commission_type)
        same_commission = False

        if commission_i:
            same_commission = commission_i.is_commission_in_type(self)

        if not same_commission:
            new_commission_i = [
                {
                    "name": self.name,
                    "policy_type": self.policy_type,
                    "date_created": Date.context_today(self),
                    "product_commission_type": self.product_commission_type,
                    "pickings_id": [(6, 0, picking_ids.ids)],
                    "clients_id": [(6, 0, self.clients_id.ids)] if self.clients_id else False,
                    "products_id": [(6, 0, self.products_id.ids)] if self.products_id else False,
                    "categories_id": [(6, 0, self.categories_id.ids)]
                    if self.categories_id
                    else False,
                    "brands_id": [(6, 0, self.brands_id.ids)] if self.brands_id else False,
                    "product_ids": [(6, 0, self.product_ids.ids)] if self.product_ids else False,
                    "commission_line_ids": self.create_image_lines(),
                }
            ]

            return commission_image.create(new_commission_i)

        same_commission.pickings_id |= picking_ids
        # pickings = picking_ids + same_commission.pickings_id
        # same_commission.write({"pickings_id": [(6, 0, pickings.ids)]})
        return same_commission

    @api.model
    def create_image_lines(self):
        commission_lines = self.commission_line_ids
        read_lines = commission_lines.read(["date_from", "date_to", "commission"])
        res = [(0, 0, line) for line in read_lines]

        return res
