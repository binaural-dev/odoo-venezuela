# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from datetime import datetime
from dateutil.relativedelta import relativedelta

import odoo
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.utils import ensure_db
from odoo.addons.web.controllers import home
from odoo.addons.auth_signup.controllers.main import AuthSignupHome


class WebBackend(home.Home):
    @http.route('/web/login', type='http', auth="public")
    def web_login(self, redirect=None, **kw):
        home.ensure_db()
        if request.httprequest.method == 'POST':
            user = request.env['res.users'].sudo().search([('login', '=', request.params['login'])])
            if user and user.pwd_expire:
                values = kw
                request.params['login_success'] = False
                values['error'] = _("Your password is expired.")
                response = request.render('web.login', values)
                response.headers['X-Frame-Options'] = 'SAMEORIGIN'
                response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
                return response
        response = super(WebBackend, self).web_login(redirect, **kw)
        return response

    @http.route(['/web', '/odoo', '/odoo/<path:subpath>', '/scoped_app/<path:subpath>'], type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        ensure_db()
        if request.env.user.id != request.env.ref('base.public_user').id and request.env.user.pwd_expire:
            request.session.logout()
        return super(WebBackend, self).web_client(s_action=s_action, **kw)


class TKAuthSignup(AuthSignupHome):

    @http.route('/web/change_password', type='http', auth='public', website=True, sitemap=False)
    def auth_password_change_user(self, *args, **kw):
        ctx = self.get_auth_signup_qcontext()
        if request.httprequest.method == 'POST':
            if kw.get('confirm_new_pwd') != kw.get('new_pwd'):
                ctx['error'] = _('Password does not match')
                response = request.render('tk_security_master.tk_change_pwd_user', ctx)
                return response

            if not kw.get('login'):
                ctx['error'] = _('Email is required')
                response = request.render('tk_security_master.tk_change_pwd_user', ctx)
                return response

            if not kw.get('old_pwd'):
                ctx['error'] = _('Old password is required')
                response = request.render('tk_security_master.tk_change_pwd_user', ctx)
                return response

            if not kw.get('new_pwd'):
                ctx['error'] = _('New password is required')
                response = request.render('tk_security_master.tk_change_pwd_user', ctx)
                return response

            if not kw.get('confirm_new_pwd'):
                ctx['error'] = _('Confirm password is required')
                response = request.render('tk_security_master.tk_change_pwd_user', ctx)
                return response
            try:
                uid = request.session.authenticate(request.session.db, kw.get('login'), kw.get('old_pwd'))
            except odoo.exceptions.AccessDenied:
                ctx['error'] = _('Invalid username or old password')
                response = request.render('tk_security_master.tk_change_pwd_user', ctx)
                return response
            usr = request.env['res.users'].sudo().search([('id', '=', uid)])
            values = {
                'pwd_expire': False,
                'password': kw.get('new_pwd'),
                'pwd_update_datetime': datetime.now(),
            }
            config_param = request.env['ir.config_parameter'].sudo()
            pwd_expire_policy = config_param.get_param('tk_security_master.pwd_expire_policy')
            if pwd_expire_policy:
                pwd_expire_days = config_param.get_param('tk_security_master.pwd_expire_days')
                values['pwd_expire_date'] = datetime.now() + relativedelta(days=int(pwd_expire_days))
            usr.sudo().write(values)
            return request.redirect('/web/login')

        response = request.render('tk_security_master.tk_change_pwd_user', ctx)
        return response
