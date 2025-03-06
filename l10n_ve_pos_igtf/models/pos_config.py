from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    igtf_percentage = fields.Float(
        "IGTF percentage", related="company_id.igtf_percentage", readonly=False
    )
    apply_igtf =  fields.Boolean(default=True)
