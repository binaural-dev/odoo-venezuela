from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = "res.company"


    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )