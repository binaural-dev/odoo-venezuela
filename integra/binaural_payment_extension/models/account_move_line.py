from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ciu_id = fields.Many2one(
        "economic.activity", string="CIU", compute="_compute_ciu_id", store=True, readonly=False
    )

    @api.depends("product_id.ciu_ids")
    def _compute_ciu_id(self):
        for line in self:
            if not line.product_id or line.ciu_id or not line.product_id.ciu_ids:
                continue
            line.ciu_id = line.product_id.ciu_ids[0]
