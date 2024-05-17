from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from lxml import etree
from collections import defaultdict

import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):

        res = super().get_view(view_id, view_type, **options)

        return res  