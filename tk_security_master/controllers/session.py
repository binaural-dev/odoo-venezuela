# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
try:
    import httpagentparser
except ImportError:
    pass

import json
import requests
from datetime import datetime
import logging

import odoo
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers import home
from odoo.addons.web.controllers import session


_logger = logging.getLogger(__name__)


def get_ip_address():
    url = 'https://api.ipify.org'
    response = requests.get(url)
    ip_address = response.text
    return ip_address


def get_ip_based_user_info(token):
    ip_address = None
    url = 'https://ipinfo.io/?token=' + token
    response = requests.get(url)
    if response.status_code == 200:
        ip_address = json.loads(response.text)
    return ip_address


def get_data_from_ip_api_vendor(ip_address):
    url = f'http://ip-api.com/json/{ip_address}'
    response = requests.get(url,  verify=False)
    if response.status_code == 200:
        ip_address = json.loads(response.text)
    return ip_address


class Home(home.Home):

    @http.route('/web/login', type='http', auth="public")
    def web_login(self, redirect=None, **kw):
        home.ensure_db()
        active_usr = True
        response = super(Home, self).web_login(redirect, **kw)
        if request.httprequest.method == 'POST':
            data = detect_user_login_attempt()
            if request.params['login_success']:
                uid = request.session.authenticate(request.session.db, request.params['login'],
                                                   request.params['password'])
                if uid is not False:
                    data['user_id'] = uid
            else:
                tried_user = request.env['res.users'].sudo().search([('login', '=', request.params['login'])], limit=1)
                if tried_user:
                    data['user_id'] = tried_user.id
                data['is_anonymous'] = True
                data['active'] = False
                data['status'] = 'inactive'
            request.env['user.sign.in.details'].sudo().create(data)

            # raise odoo.exceptions.AccessDenied as e:
            #     if e.args == odoo.exceptions.AccessDenied().args:
            #         values['error'] = _("Wrong login/password")
        return response

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        response = super(Home, self).web_client(s_action, **kw)
        user_session = request.env['user.sign.in.details'].sudo().search([('user_id', '=', request.uid),
                                                                          ('session', '=', False)], order='id desc',
                                                                         limit=1)
        if user_session:
            user_session.session = request.session.sid
        return response


class Session(session.Session):

    @http.route('/web/session/logout', type='http', auth="none")
    def logout(self, redirect='/web'):
        session_details = request.env['user.sign.in.details'].sudo().search([('session', '=', request.session.sid)],
                                                                            limit=1)
        if session_details:
            session_details.write({'status': 'inactive', 'active': False, 'logout_datetime': datetime.now()})
        response = super(Session, self).logout(redirect)
        return response

    @http.route('/user/read/operation', type='json', auth="none")
    def user_read_operation_log(self, **kw):
        session_id = request.session.sid
        browser_hash = kw.get('url_hash', {})
        dntm, user_logged_id = None, None
        res_model = browser_hash.get('model', False)
        dntm_model = request.env['ir.model'].sudo().search([('model', '=', 'do.not.track.models')]).id
        if dntm_model and res_model:
            dntm = request.env['do.not.track.models'].sudo().search([('res_model', '=', res_model)]).id

        if session_id:
            user_logged_id = request.env['user.sign.in.details'].sudo().search([('session', '=', session_id)],
                                                                               limit=1)

        if user_logged_id:
            user_logged_id.write({'last_active_time': datetime.now()})

            if browser_hash.get('action') and browser_hash.get('action') != 'menu' and browser_hash.get(
                    'action') != 'studio':
                act_rec = request.env['ir.actions.actions'].sudo().browse(int(browser_hash.get('action')))
                if act_rec:
                    title = act_rec.name
                else:
                    title = 'N/A'
            else:
                title = 'N/A'

            if not dntm and user_logged_id.user_id.tu_read_logs:
                request.env['user.audit'].sudo().create({
                    'title': title,
                    'res_url': kw.get('browser_url') if kw.get('browser_url') else '',
                    'res_model': browser_hash.get('model') if res_model else '',
                    'res_id': browser_hash.get('id') if browser_hash.get('id') else '',
                    'view_type': browser_hash.get('view_type') if browser_hash.get('view_type') else "",
                    'action_type': 'read',
                    'user_session_id': user_logged_id.id,
                    'user_id': user_logged_id.user_id.id,
                })


def detect_user_login_attempt():
    data = {}
    agent = request.httprequest.environ.get('HTTP_USER_AGENT')
    agent_details = httpagentparser.detect(agent)
    platform = get_os_details(agent_details['platform']['name'])
    data['platform'] = platform
    if platform == "Other":
        data['other_platform'] = agent_details['platform']['name']
    data['platform_version'] = agent_details['platform']['version']
    data['is_bot'] = agent_details['bot']
    browser = find_browser(agent_details['browser']['name'])
    data['browser'] = browser
    if browser == "Other":
        data['other_browser'] = agent_details['browser']['name']
    data['browser_version'] = agent_details['browser']['version']
    try:
        ip_address = request.httprequest.environ.get('HTTP_X_REAL_IP')
        if not ip_address:
            ip_address = get_ip_address()
        _logger.info('User logged ip_address: %s', ip_address)
        data['ip_address'] = ip_address
    except requests.exceptions.ConnectionError:
        pass
    data['logged_datetime'] = datetime.now()
    data['last_active_time'] = datetime.now()
    data['active'] = True
    data['status'] = 'active'
    user_data = None
    try:
        user_data = get_data_from_ip_api_vendor(data['ip_address'])
    except requests.exceptions.ConnectionError:
        pass
    if user_data:
        data['city'] = user_data.get('city', '')
        data['region'] = user_data.get('region', '')
        data['country'] = user_data.get('country', '')
        data['isp'] = user_data.get('isp', '')
        data['postal_code'] = user_data.get('zip', '')
        data['timezone'] = user_data.get('timezone', '')
        data['latitude'] = user_data.get('lat', '')
        data['longitude'] = user_data.get('lon', '')
    return data


def find_browser(browser_name):
    browsers = ('Chrome', 'Firefox', 'Safari', 'ChromiumEdge', 'Opera')
    if browser_name in browsers:
        return browser_name
    else:
        return "Other"


def get_os_details(platform):
    platforms = ('Windows', 'Linux', 'Mac OS', 'Android', 'iOS')
    if platform in platforms:
        return platform
    else:
        return "Other"
