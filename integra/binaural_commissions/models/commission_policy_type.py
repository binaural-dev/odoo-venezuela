from odoo import fields, models, api, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class CommissionPolicyType(models.Model):
    _name = "commission.policy.type"
    _description = "Commission Policy Type"
    _order = "sequence"

    name = fields.Char()
    policy_type = fields.Selection(
        selection=[
            ("product", "Product"),
            ("client", "Client"),
            ("pricelist", "Pricelist"),
            ("all", "General"),
        ],
        default="all",
        required=True,
    )
    sequence = fields.Integer(default=10)

    def write(self, vals):
        res = super().write(vals)
        _logger.info(self.policy_type)
        if self.search([],limit=1).policy_type != "product":
            raise UserError(_("The policy type 'product' must be first"))
        if self.search([],limit=1, order="sequence desc").policy_type != "all":
            raise UserError(_("The policy type 'all' must be last"))
        return res 
