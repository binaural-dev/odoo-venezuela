import logging
from email.policy import default

from odoo import _, api, fields, models
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


class PriceRule(models.Model):
    _inherit = "delivery.price.rule"

    is_foreign_currency = fields.Boolean("Use Foreign Currency")
    foreign_list_base_price = fields.Float(digits="Product Price", required=True, default=1.0)
    list_base_price = fields.Float(compute="_compute_base_price", store=True)

    kg_apply_extra = fields.Boolean(
        string='Does apply extra charge per Kg?',
        default=False
    )
    
    kg_extra_charge = fields.Float(
        'Kg Extra charge amount',
        default=1
    )

    kg_extra_charge_amount = fields.Float(
        'Extra charge amount per kg'
    )

    def write(self, vals):
        if "foreign_list_base_price" in vals.keys():
            return super().write(vals)

        if "is_foreign_currency" in vals.keys() and not vals.get("is_foreign_currency"):
            vals.update({"foreign_list_base_price": 1.0})
        
        return super().write(vals)

    @api.depends("foreign_list_base_price", "carrier_id.foreign_rate", "is_foreign_currency")
    def _compute_base_price(self):
        for rule in self:
            foreign_rate = rule.carrier_id.foreign_rate
            digits = rule.carrier_id._fields["foreign_rate"].get_digits(self.env)[1]
            inverse_list_base_price = rule.list_base_price or 0.0

            if (
                not float_is_zero(foreign_rate, precision_digits=digits)
                and rule.is_foreign_currency
            ):
                inverse_list_base_price = rule.foreign_list_base_price / foreign_rate

            rule.update({"list_base_price": inverse_list_base_price})
