from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    config_deductible_tax = fields.Boolean(related='company_id.config_deductible_tax')

    not_deductible_tax = fields.Boolean(default=False)

    international_purchase_exempt_product = fields.Boolean(
        string="International Purchase Exempt Product"
    )

    @api.depends(
        "product_id", "product_uom_id", "international_purchase_exempt_product"
    )
    def _compute_tax_ids(self):
        """
        We inherit this method to add the international purchase exempt product to the depends
        """
        super()._compute_tax_ids()

    def _get_computed_taxes(self):
        """
        We inherit this method to return the international purchase exempt product when the
        move line is an international purchase exempt product
        """
        res = super()._get_computed_taxes()
        if (
            self.international_purchase_exempt_product
            and self.company_id.exent_aliquot_purchase_international
        ):
            res = self.company_id.exent_aliquot_purchase_international
        return res
