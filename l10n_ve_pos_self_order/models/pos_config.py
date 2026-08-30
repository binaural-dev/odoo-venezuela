from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    self_ordering_hide_catalog = fields.Boolean(
        string="Kiosk: hide catalog (scan / search only)",
        help="In Kiosk mode, hide the product catalog and let customers add "
        "products only by scanning a barcode or using the search box.",
    )

    def _load_pos_self_data_fields(self, pos_config_id):
        # Expose the flag to the Self Order / Kiosk frontend (this.selfOrder.config).
        fields_list = super()._load_pos_self_data_fields(pos_config_id)
        fields_list.append("self_ordering_hide_catalog")
        return fields_list
