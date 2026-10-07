from odoo import api, models


class ResCountryMunicipality(models.Model):
    """Expone ``res.country.municipality`` (``l10n_ve_location``) al mecanismo
    de datos del Kiosko.

    ``res.country.state`` ya llega al frontend del Kiosko porque el core
    ``pos_self_order`` lo trae en ``pos.config._load_self_data_models()``. El
    municipio es un modelo propio de ``l10n_ve_location`` que nunca implementó
    ``pos.load.mixin`` (no lo necesitaba fuera de este caso), así que hay que
    dárselo aquí — mismo patrón que el core usa para ``res.country.state``
    (``point_of_sale/models/res_country_state.py``): heredar el mixin y
    declarar los campos a exponer. Se añade a la lista de modelos del Kiosko
    en ``pos.config._load_self_data_models`` (ver ``models/pos_config.py``).
    """

    _name = "res.country.municipality"
    _inherit = ["res.country.municipality", "pos.load.mixin"]

    @api.model
    def _load_pos_self_data_fields(self, config):
        return ["id", "name", "code", "state_id", "country_id"]
