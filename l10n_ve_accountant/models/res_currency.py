from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # Homologación: No permitir eliminar el registro de una moneda, ni modificar, agregar o eliminar sus tasas de cambio, a menos que pertenezca al grupo
    edit_rate = fields.Boolean(
        compute="_compute_edit_rate",
    )

    def _compute_edit_rate(self):
        for record in self:
            record.edit_rate = (
                record.env.user.has_group(
                    "l10n_ve_accountant.group_fiscal_config_support"
                )
            )

    def unlink(self):
        raise UserError(_("It is not possible to delete currency records."))
        return super(ResCurrency, self).unlink()
    # Cierre de código homologado. En caso de requerir cambios o ajustes consultar con la Gerencia de Producto
