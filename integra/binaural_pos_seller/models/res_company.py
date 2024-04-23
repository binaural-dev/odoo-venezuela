from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_seller_from_order = fields.Selection(
        selection=[("from_order", "From Order"), ("from_pos", "From POS")], default="from_order"
    )
