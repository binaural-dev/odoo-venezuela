from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.constrains("foreign_currency_id")
    def _check_foreign_currency_id_required(self):
        """Este módulo asume que toda compañía tiene una moneda comercial
        configurada (l10n_ve_rate). A diferencia del constrains de
        l10n_ve_rate (que solo exige que sea distinta a la moneda de la
        compañía), aquí se exige que exista, para cualquier compañía nueva
        que se cree después de instalar el módulo."""
        for company in self:
            if not company.foreign_currency_id:
                raise ValidationError(
                    _(
                        "La compañía %(name)s no tiene una moneda comercial "
                        "(moneda alterna) configurada. Este módulo requiere "
                        "que toda compañía la tenga definida en Binaural "
                        "Settings antes de poder usar el CRM.",
                        name=company.name,
                    )
                )
