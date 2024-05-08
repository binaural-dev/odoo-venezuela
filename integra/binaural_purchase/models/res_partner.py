from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("property_purchase_currency_id")
    def _check_property_purchase_currency_id(self):
        for partner in self:
            if partner.property_purchase_currency_id:
                raise ValidationError(
                    _(
                        "You cannot set the purchase currency for a partner, as it the purchase "
                        "orders must use the base currency of the company."
                    )
                )
