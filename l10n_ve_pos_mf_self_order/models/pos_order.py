from odoo import api, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _load_pos_self_data_fields(self, config):
        """Expone los datos fiscales de la orden al cliente del Kiosko.

        El Kiosko imprime la factura fiscal en LOCAL (Web Serial) y guarda el
        número devuelto por la máquina en la orden en memoria. Para que ese
        número viaje al servidor con la orden (``serializeForORM`` solo incluye
        campos que el esquema del cliente conoce) y ``_prepare_invoice_vals`` lo
        estampe en el ``account.move`` al sincronizar, el esquema del cliente
        del Kiosko debe conocer estos campos. ``l10n_ve_pos_mf`` ya los expone
        en el loader de caja; aquí se replica para el Kiosko.
        """
        fields_list = list(super()._load_pos_self_data_fields(config))
        for field_name in ("mf_invoice_number", "fiscal_machine", "mf_reportz"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
