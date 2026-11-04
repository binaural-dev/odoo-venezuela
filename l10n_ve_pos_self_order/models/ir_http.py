from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    # Sin esto, /website/translations (la ruta pública que usa el Kiosko) nunca
    # carga el .po de este módulo: mismo mecanismo que pos_self_order y
    # point_of_sale (ver sus models/ir_http.py).
    @classmethod
    def _get_translation_frontend_modules_name(cls):
        mods = super()._get_translation_frontend_modules_name()
        return mods + ["l10n_ve_pos_self_order"]
