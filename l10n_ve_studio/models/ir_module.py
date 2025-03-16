from odoo import models, api, exceptions, _
from odoo.exceptions import UserError


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    RESTRICTED_MODULES = ["web_studio"]

    def _check_restricted(self):
        restricted = self.filtered(lambda m: m.name in self.RESTRICTED_MODULES)
        if restricted:
            raise UserError(_("Block installing of module '%s'", restricted.name))

    def button_immediate_install(self):
        self._check_restricted()
        return super().button_immediate_install()
