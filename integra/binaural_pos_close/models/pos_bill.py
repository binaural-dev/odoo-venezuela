from odoo import fields, models


class PosBill(models.Model):
    _inherit = "pos.bill"

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id.id
    )
