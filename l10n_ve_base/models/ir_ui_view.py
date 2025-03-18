from odoo import models, api, _
from odoo.exceptions import UserError, ValidationError


class IrUIView(models.Model):
    _inherit = "ir.ui.view"

    # @api.model
    # def create(self, vals):
    #     if not self.env.user._is_superuser():
    #         raise UserError(_("Only the superuser can create system views."))
    #     return super(IrUIView, self).create(vals)

    # def write(self, vals):
    #     if not self.env.user._is_superuser():
    #         raise UserError(_("Only the superuser can modify system views."))
    #     return super(IrUIView, self).write(vals)

    # def unlink(self):
    #     if not self.env.user._is_superuser():
    #         raise UserError(_("Only the superuser can delete system views."))
    #     return super(IrUIView, self).unlink()
