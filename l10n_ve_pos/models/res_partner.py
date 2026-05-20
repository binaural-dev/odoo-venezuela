from odoo import models, fields, api, _
from ...tools import binaural_cne_query
from odoo.exceptions import MissingError

class ResPartner(models.Model):
    _inherit = "res.partner"

    pos_user_group_xml_ids = fields.Json(
        compute="_compute_pos_user_group_xml_ids",
        string="POS User Group XML IDs",
    )

    @api.depends("user_ids", "user_ids.all_group_ids")
    def _compute_pos_user_group_xml_ids(self):
        for partner in self:
            groups = partner.sudo().user_ids.all_group_ids
            external_ids = groups.get_external_id()
            partner.pos_user_group_xml_ids = sorted(
                xml_id for xml_id in external_ids.values() if xml_id
            )

    def get_default_name_by_vat_param(self, prefix_vat, vat):
        """
        Retrieves the default name from the Venezuelan CNE (National Electoral Council) based on the vat and prefix.
        
        :param prefix_vat: The vat prefix (e.g., 'V', 'J')
        :param vat: The vat number
        :return: str name from CNE
        :raises MissingError: If there's an issue connecting with the CNE service
        """
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
        """
        Overridden to ensure city_id is an integer when creating or updating from the POS UI.
        
        :param partner: dict containing the partner data from the POS
        :return: Response from super().create_from_ui
        """
        if partner.get("city_id", False):
            partner["city_id"] = int(partner["city_id"])
        return super().create_from_ui(partner)

    @api.model
    def _load_pos_data_fields(self, config_id):
        """
        Extends the list of fields to be loaded for res.partner in the POS.
        
        :param config_id: The ID of the current pos.config
        :return: List of field names
        """
        res = super()._load_pos_data_fields(config_id)
        res += ["city_id", "pos_user_group_xml_ids"]
        return res
