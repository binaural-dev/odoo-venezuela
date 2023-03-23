from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    module_binaural_igtf = fields.Boolean("IGTF")
