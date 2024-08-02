import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartnerInherit(models.Model):
    _inherit = "res.partner"

    seller_ids = fields.Many2many(
        "hr.employee",
        string="Sellers",
        tracking=True,
        help="Sellers associated with the partner.",
        default=lambda self: self.env.company.initial_seller,
        domain=[("is_seller", "=", True)],
    )

    company_seller = fields.Boolean(
        related="company_id.company_seller",
    )

    @api.model
    def _commercial_fields(self):
        """Returns the list of fields that are managed by the commercial entity
        to which a partner belongs. These fields are meant to be hidden on
        partners that aren't `commercial entities` themselves, and will be
        delegated to the parent `commercial entity`. The list is meant to be
        extended by inheriting classes."""

        res = super()._commercial_fields()
        res.append("seller_ids")

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            default_seller = [(6, 0, self.env.company.initial_seller.ids)]
            vals["seller_ids"] = vals.get("seller_ids", default_seller)

        partners = super().create(vals_list)
        partners.sellers_validate()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if not self.seller_ids or "seller_ids" in vals:
            for partner in self:
                partner.sellers_validate()
        return res

    def sellers_validate(self):
        for partner in self.filtered(
            lambda p: p != self.env.ref("binaural_seller.res_partner_1", raise_if_not_found=False)
        ):
            if partner.company_seller:
                employee_seller = self.env["hr.employee"].search(
                    [("company_id", "=", self.env.company.id), ("is_seller", "=", True)], limit=1
                )
                if employee_seller:
                    if not self.env.company.multiple_sellers and len(partner.seller_ids) > 1:
                        raise UserError(
                            _("You are only allowed to assign a salesperson to the customer")
                        )
                    if not len(partner.seller_ids):
                        raise UserError(
                            _("The customer must have at least one salesperson assigned")
                        )
