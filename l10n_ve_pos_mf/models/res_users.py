from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _load_pos_data_read(self, records, config):
        """Expone si el usuario puede cerrar la sesion de PDV con el boton
        nativo de Odoo (sin Reporte Z ni validacion de pedidos sin
        facturar), ademas del flujo dual existente.

        Clave con prefijo "_" obligatorio: es el unico formato que el
        related_models del cliente conserva sin descartar (mismo mecanismo
        que usa _role en el core, ver l10n_ve_pos/models/res_users.py).
        """
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            user = records[0]
            read_records[0]['_can_close_session_native'] = user.has_group(
                'l10n_ve_pos_mf.group_pos_close_native'
            )
        return read_records
