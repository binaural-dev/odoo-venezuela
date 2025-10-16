from odoo import http
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)


class AccessStatusScreen(http.Controller):

    @http.route("/access_status_screen", type="http", auth="public", website=True)
    def show_screen(self, **kw):
        return request.render("cadipa_hikvision.status_screen_page", {'no_footer': True, 'no_header': True})