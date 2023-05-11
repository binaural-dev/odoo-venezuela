import json

from odoo import http
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)

class PortalBudget(http.Controller):
    
    @http.route(['/budget'], type='http', auth="user", website=True)
    def portal_budget(self, **kw):
        return request.render("binaural_mobile.portal_budget_form", {})