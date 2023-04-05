import logging
import json

from odoo import _, api, fields, models
from odoo.osv import expression

_logger = logging.getLogger(__name__)
FILTER_PARTNER = {
    "customer": [("customer_rank", ">=", 1)],
    "supplier": [("supplier_rank", ">=", 1)],
    "contact": [("customer_rank", "=", 0), ("supplier_rank", "=", 0)],
}


class FilterPartnerMixin(models.AbstractModel):
    _name = "filter.partner.mixin"
    _description = "Mixin that allows to filter partner type"

    partner_id_domain = fields.Char(compute="_compute_partner_id_domain")
    filter_partner = fields.Selection(
        [("customer", "Cliente"), ("supplier", "Proveedor"), ("contact", "Contacto")],
        help="Filter partner by both customer or supplier rank (Depending on what is needed)",
    )

    @api.depends("filter_partner")
    def _compute_partner_id_domain(self):
        for record in self:
            domain = record.get_partner_domain()
            record.update({"partner_id_domain": json.dumps(domain)})

    def get_partner_domain(self, extend: list = None, conditional: str = "&") -> list:
        """Get the domain for the partner_id field based on the filter_partner field.

        Parameters
        ----------
        extend : list, optional
            domains to extend the default domain, by default None

        Returns
        -------
        list
            The domain for the partner_id field.
        """

        self.ensure_one()
        if not extend:
            return FILTER_PARTNER.get(self.filter_partner, [])
        if conditional == "&":
            return expression.AND([FILTER_PARTNER.get(self.filter_partner, []), extend])
        return expression.OR([FILTER_PARTNER.get(self.filter_partner, []), extend])
