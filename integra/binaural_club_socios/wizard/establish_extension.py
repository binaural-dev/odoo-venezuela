from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class EstablishExtension(models.Model):
    _name = "establish.extension"

    reason = fields.Text()