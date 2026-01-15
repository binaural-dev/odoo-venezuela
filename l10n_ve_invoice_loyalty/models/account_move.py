from datetime import datetime
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.constrains("invoice_line_ids")
    def _check_price_in_zero(self):
        """Allow zero price lines for loyalty reward discounts."""

        for line in self.filtered(lambda m: m.is_invoice()).mapped("invoice_line_ids"):
            if line.price_unit <= 0 and line.display_type not in (
                "line_section",
                "line_note",
            ):
                is_loyalty_reward = (
                    self.env["loyalty.reward"].search_count(
                        [("discount_line_product_id", "=", line.product_id.id)]
                    ) > 0
                )

                if is_loyalty_reward:
                    return super(
                        AccountMove, self.with_context(from_loyalty=True)
                    )._check_price_in_zero()

                return super(AccountMove, self)._check_price_in_zero()
