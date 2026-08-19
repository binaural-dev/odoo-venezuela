from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    # Sin esto, /website/translations (la ruta pública que usa el Kiosko) nunca
    # carga el .po de este módulo, y sus strings JS/plantilla (estado fiscal,
    # imprimir/reimprimir, panel de debug) se ven en inglés aunque el .po esté
    # completo. Mismo mecanismo que pos_self_order, point_of_sale y
    # l10n_ve_pos_self_order (ver sus models/ir_http.py): cada módulo con
    # traducciones de frontend debe añadirse a sí mismo a la lista.
    @classmethod
    def _get_translation_frontend_modules_name(cls):
        mods = super()._get_translation_frontend_modules_name()
        return mods + ["l10n_ve_pos_mf_self_order"]
