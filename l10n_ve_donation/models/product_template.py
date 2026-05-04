from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_donation_product = fields.Boolean(string="Is Donation Product", tracking=True)

    @api.constrains("is_donation_product")
    def _check_unique_donation_product(self):
        for record in self:
            if record.is_donation_product:
                donation_product = record.with_company(record.company_id).search(
                    [
                        ("is_donation_product", "=", True),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if donation_product:
                    raise ValidationError(
                        _(
                            "There is already a donation product. Please deactivate the previous one before creating a new one."
                        )
                    )
