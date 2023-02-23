from odoo import api, fields, models, _
from ...tools import binaural_bcv_query
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_foreign_id = fields.Many2one(
        "res.currency", string="Currency Foreign", help="Currency Foreign for the company"
    )

    currency_provider = fields.Selection(selection_add=[("bcv", "Venezuelan Central Bank")])

    def _parse_bcv_data(self, availible_currencies):
        _logger.info("Parsing BCV data")
        return binaural_bcv_query.get_usd_rate_of_the_day_bcv()
