from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def check_duplicate_email(self, email, company_id=None, parent_id=False):
        """Sobrescribe la validación original del módulo l10n_ve_contact para omitir
        la comprobación de correos duplicados cuando l10n_ve_invoice_digital está instalado.
        """
        return
