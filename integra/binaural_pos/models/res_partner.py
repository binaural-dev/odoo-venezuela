from odoo import models, fields, api, _
from ...tools import binaural_cne_query
from odoo.exceptions import MissingError

import logging
_logger = logging.getLogger(__name__)


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

        _logger.info(name)

        return name
