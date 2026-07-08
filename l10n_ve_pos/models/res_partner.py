from odoo import models, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Odoo 19 loader contract: extend the read with the Venezuelan
        ``prefix_vat`` (Selection) and ``city_id`` fields used by the POS UI.
        """
        res = super()._load_pos_data_fields(config_id)
        extra = [name for name in ('prefix_vat', 'city_id') if name not in res]
        return res + extra
