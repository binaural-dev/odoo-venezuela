from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_deductible = fields.Boolean(
        string="Use Deductibles",
        help="Allows applying a global deductible (percentage or fixed amount) "
        "to vendor bills.",
    )
