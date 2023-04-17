from odoo import api, fields, models, _
from ...tools import binaural_bcv_query
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_foreign_id = fields.Many2one(
        "res.currency",
        string="Currency Foreign",
        help="Currency Foreign for the company"
    )

    currency_provider = fields.Selection(
        selection_add=[("bcv", "Venezuelan Central Bank")]
    )

    @api.model
    def _parse_bcv_data(self, availible_currencies):
        usd_rate_bcv = binaural_bcv_query.get_usd_rate_of_the_day_bcv(self)
        
        return {
            "USD": (1, usd_rate_bcv[1]),
            "VEF": usd_rate_bcv
        }