from odoo import fields, models, api, SUPERUSER_ID
from odoo import api, fields, models, modules, tools, _
from requests import request, HTTPError
import json

import logging

_logger = logging.getLogger(__name__)


class Module(models.Model):
    _inherit = "ir.module.module"

    binaural = fields.Boolean(default=False)