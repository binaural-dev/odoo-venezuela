import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.web.controllers.report import ReportController
from . import utils

_logger = logging.getLogger(__name__)

class ReportController(ReportController):
    @http.route([
        '/report/<converter>/<reportname>',
        '/report/<converter>/<reportname>/<docids>',
    ], type='http', auth='user', website=True)
    def report_routes(self, reportname, docids=None, converter=None, **data):
        request.update_env(user=2)