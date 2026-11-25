from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_self_data_read(self, records, config):
        """El kiosko lee las monedas sin pasar por ``_load_pos_data_read``: se le
        aplica la misma tasa del día de la sesión que al PdV (ticket 16351), para
        que la lista de precios en divisa y el total en divisa usen la misma
        tasa, también después de medianoche."""
        read_records = super()._load_pos_self_data_read(records, config)
        return self._apply_pos_session_rates(read_records, records, config)
