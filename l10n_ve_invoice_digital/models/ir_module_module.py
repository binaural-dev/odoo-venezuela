from odoo import models, _
from odoo.exceptions import AccessError

MODULE_NAME = "l10n_ve_invoice_digital"


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _check_tfhka_uninstall_rights(self):
        """Solo un TFHKA Admin puede desinstalar el módulo de facturación digital."""
        for module in self:
            if module.name == MODULE_NAME and not self.env.user.has_group(
                "l10n_ve_invoice_digital.group_l10n_ve_invoice_digital_admin"
            ):
                raise AccessError(_(
                    "Only a TFHKA Admin can uninstall the digital invoicing module. "
                    "Uninstalling it would permanently remove the digitalized invoices "
                    "and their fiscal traceability."
                ))

    def button_uninstall(self):
        self._check_tfhka_uninstall_rights()
        return super().button_uninstall()

    def button_immediate_uninstall(self):
        self._check_tfhka_uninstall_rights()
        return super().button_immediate_uninstall()
