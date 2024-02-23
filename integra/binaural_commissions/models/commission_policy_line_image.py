from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)

POLICY_TYPE = {"client": _("Cliente"), "product": _("Producto"), "all": _("General")}


class CommissionPolicyLineImage(models.Model):
    _name = "commission.policy.line.image"
    _description = "Commission Policy Line Image"
    _rec_name = "commission"
    _order = "date_from asc"

    date_from = fields.Integer(required=True, default=1)
    date_to = fields.Integer(required=True)
    commission = fields.Float(required=True, help="Commission percentage")
    policy_type = fields.Selection(
        selection=[("client", "Client"), ("product", "Product"), ("all", "General")],
        string="Commission Type",
    )
    infinite = fields.Boolean()

    def name_get(self):
        values = []
        for record in self:
            range_date = f"[{record.date_from} => {record.date_to if not record.infinite else '∞'}]"
            if record.date_to == record.date_from and not record.infinite:
                range_date = f"[{record.date_from}]"
            values.append((record.id, f"{POLICY_TYPE.get(record.policy_type,'')} {record.commission} % {range_date}"))
        return values

