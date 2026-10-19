from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    self_ordering_hide_catalog = fields.Boolean(
        string="Kiosk: hide catalog (scan / search only)",
        help="In Kiosk mode, hide the product catalog and let customers add "
        "products only by scanning a barcode or using the search box.",
    )

    self_ordering_require_address = fields.Boolean(
        string="Kiosk: require customer address",
        help="In Kiosk mode, require the state, municipality and street when "
        "creating a new contact.",
    )

    def _load_pos_self_data_fields(self, pos_config_id):
        # Expose the flags to the Self Order / Kiosk frontend (this.selfOrder.config).
        fields_list = super()._load_pos_self_data_fields(pos_config_id)
        fields_list.append("self_ordering_hide_catalog")
        fields_list.append("self_ordering_require_address")
        # Kiosk payment page (foreign-currency total): the manifest loads
        # l10n_ve_pos's model patches (static/src/overrides/models/*) into the
        # Kiosk bundle, and PosOrder.localToForeign() reads the currency and
        # rates from the order's pos.config, exactly as on the cashier.
        fields_list.append("foreign_currency_id")
        fields_list.append("foreign_rate")
        fields_list.append("foreign_inverse_rate")
        return fields_list

    def _load_self_data_models(self):
        # res.country.state already ships with the core Kiosk data (pos_self_order
        # loads it for every self-ordering mode). res.country.municipality is
        # l10n_ve_location-only and never implemented pos.load.mixin, so it needs
        # to be added here for the Kiosk's address step (see
        # models/res_country_municipality.py).
        models_list = super()._load_self_data_models()
        models_list.append("res.country.municipality")
        return models_list
