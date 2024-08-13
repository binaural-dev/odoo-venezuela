import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import MissingError
from ...tools import binaural_cne_query

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
            if vals.get("vat") and not vals.get("name", False):
                prefix_vat = vals.get("prefix_vat")
                name = vals.get("name")
                vat = vals.get("vat")
                if prefix_vat == "V" and not name and prefix_vat in ["V", "E"]:
                    name, flag = binaural_cne_query.get_default_name_by_vat(self, prefix_vat, vat)
                    if not flag:
                        continue
                    vals["name"] = name
        return super(ResPartner, self).create(vals_list)

    def _check_vat(self):
        pattern = "^[0-9]*$"
        for record in self:
            if record.vat:
                if not re.match(pattern, record.vat):
                    raise MissingError(_("The vat field only accepts numbers"))

    @api.onchange("vat", "prefix_vat")
    def _onchange_(self):
        """This function assign the name of the person by the vat number and the prefix of the vat number
        calling the function get_default_name_by_vat from binaural_cne_query

        Args:
            prefix_vat (string): prefix of the vat number (V)
            vat (string): vat number of the person, this number is unique in Venezuela
        """
        if self.vat and not self.name and self.prefix_vat in ["V", "E"]:
            self._check_vat()
            name, flag = binaural_cne_query.get_default_name_by_vat(self, self.prefix_vat, self.vat)
            if not flag:
                return
            for record in self:
                record.name = name
