from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    # fields models
    is_owner = fields.Boolean()
    proprietary_acronym = fields.Char()
