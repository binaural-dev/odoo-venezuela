import logging
import werkzeug
from werkzeug.urls import url_encode

from odoo import http, tools, _
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request

_logger = logging.getLogger(__name__)

class AuthSignupHome(AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        if request.website.account_on_checkout == 'mandatory':
            raise werkzeug.exceptions.NotFound()
        
        return super().web_auth_signup(*args, **kw)