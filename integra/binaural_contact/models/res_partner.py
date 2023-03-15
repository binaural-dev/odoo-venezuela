from odoo import models, fields, api, _
from odoo.exceptions import MissingError
from ...tools import binaural_cne_query
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    prefix_vat = fields.Selection(
        [
            ("V", "V"),
            ("E", "E"),
            ("J", "J"),
            ("G", "G"),
            ("P", "P"),
            ("C", "C"),
        ],
        string="Prefix VAT",
        default="V",
        help="Prefix of the VAT number",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """This function assign the name of the person by the vat number and the prefix of the vat number
        calling the function get_default_name_by_vat from binaural_cne_query before create the partner

        Args:
            prefix_vat (string): prefix of the vat number (V)
            vat (string): vat number of the person, this number is unique in Venezuela

        Raises:
            UserError: Error to connect with CNE, please check your internet connection or try again later

        """
        for vals in vals_list:
            if vals.get("vat"):
                prefix_vat = vals.get("prefix_vat")
                vat = vals.get("vat")
                if prefix_vat == "V":
                    name, flag = binaural_cne_query.get_default_name_by_vat(self, prefix_vat, vat)
                    if not flag:
                        raise MissingError(
                            _(
                                "Error to connect with CNE, please check your internet connection or try again later"
                            )
                        )
                    vals["name"] = name
                return super(ResPartner, self).create(vals_list)

    def get_default_name_by_vat(self):

        """This function assign the name of the person by the vat number and the prefix of the vat number
        calling the function get_default_name_by_vat from binaural_cne_query

        Args:
            prefix_vat (string): prefix of the vat number (V)
            vat (string): vat number of the person, this number is unique in Venezuela

        Raises:
            UserError: Error to connect with CNE, please check your internet connection or try again later

        """
        name, flag = binaural_cne_query.get_default_name_by_vat(self, self.prefix_vat, self.vat)
        if not flag:
            raise MissingError(
                _(
                    "Error to connect with CNE, please check your internet connection or try again later"
                )
            )
        for record in self:
            record.name = name
