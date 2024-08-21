
import werkzeug
from odoo import http, fields, tools
from odoo.http import request
from odoo.addons.web.controllers.home import Home, ensure_db
from odoo import SUPERUSER_ID


class TitanHome(Home):

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        ensure_db()
        if not request.session.uid:
            return werkzeug.utils.redirect('/web/login', 303)
        if kw.get('debug') and kw.get('debug') != "0":
            admin_id = request.env.ref('base.user_admin')
            if not request.session.uid==admin_id.id and not request.env.user.browse(request.session.uid).has_group('tc_disable_debug_mode.group_debug_mode_user'):
                return werkzeug.utils.redirect('/web?debug=0')
        return super(TitanHome, self).web_client(s_action=s_action, **kw)