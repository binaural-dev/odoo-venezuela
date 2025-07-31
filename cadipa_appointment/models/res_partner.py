import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import MissingError, ValidationError
from ...tools import binaural_cne_query

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    guest_state = fields.Selection(
        [
            ('confirmed', 'Confirmed'),
            ('pending', 'Pending'),
            ('canceled', 'Canceled'),
        ],
        default='confirmed',
    )

    guest_type = fields.Selection(
        [
            ('family', 'Family'),
            ('guest', 'Guest'),
        ],
        default='guest',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """inherit for renaming VAT in website context"""
        res = super(ResPartner, self).create(vals_list)
        context = self.env.context
        if context.get('website_rename_vat'):
            for record in res:
                for vals in vals_list:
                    record.vat = vals.get("vat", record.vat)
        return res