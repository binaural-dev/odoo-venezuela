from odoo import models, api, _
from odoo.exceptions import UserError, ValidationError


class IrUIView(models.Model):
    _inherit = "ir.ui.view"
