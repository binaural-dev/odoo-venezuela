from odoo import models, fields, api, _
from ...tools import binaural_cne_query
from odoo.exceptions import MissingError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def get_default_name_by_vat_param(self, prefix_vat, vat):
        name, flag = binaural_cne_query.get_default_name_by_vat(self, prefix_vat, vat)
        if not flag:
            raise MissingError(
                _(
                    "Error to connect with CNE, please check your internet connection or try again later"
                )
            )

        return name

    @api.model
    def create_from_ui(self, partner):
        if partner.get("city_id", False):
            partner["city_id"] = int(partner["city_id"])
        return super().create_from_ui(partner)
    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res += ['city_id']
        return res
