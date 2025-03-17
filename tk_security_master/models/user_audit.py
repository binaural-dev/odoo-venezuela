# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta
from odoo import fields, models, api, http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class UserAudit(models.Model):
    """User Actions Logs Details"""
    _name = 'user.audit'
    _description = __doc__
    _order = 'id desc'
    _rec_name = 'title'

    title = fields.Char(string="Record Details")
    user_session_id = fields.Many2one('user.sign.in.details', string="User Sessions")
    user_id = fields.Many2one('res.users', string="User")
    res_model = fields.Char(string="Res Model")
    res_id = fields.Char(string="Record IDs")
    action_type = fields.Selection([('create', 'Create'), ('read', 'Read'), ('update', 'Update'), ('delete', 'Delete')],
                                   string="Action")
    res_url = fields.Char(string="Url")
    view_type = fields.Char(string="View")
    user_audit_log_ids = fields.One2many('user.audit.logs', 'user_audit_id', string="Logs Details")

    def auto_delete_user_logs(self):
        config_param = self.env['ir.config_parameter'].sudo()
        auto_delete_log = config_param.get_param('tk_security_master.enable_auto_delete')

        if not auto_delete_log:
            return

        create_log = config_param.get_param('tk_security_master.create_log')
        read_log = config_param.get_param('tk_security_master.read_log')
        update_log = config_param.get_param('tk_security_master.update_log')
        delete_log = config_param.get_param('tk_security_master.delete_log')
        auto_delete_log_days = int(config_param.get_param('tk_security_master.auto_delete_log_days', default=30))
        # Calculate the date threshold
        date_threshold = datetime.now() - timedelta(days=auto_delete_log_days)
        # Search for logs older than the threshold
        old_logs = self.search([('create_date', '<', date_threshold)])

        action_flags = {
            'create': create_log,
            'read': read_log,
            'update': update_log,
            'delete': delete_log
        }

        for log in old_logs:
            if action_flags.get(log.action_type, False):
                log.unlink()
            else:
                return

    def open_record(self):
        if self.action_type in ('create', 'update') and self.res_id is not None:
            action = {
                'name': _('View Logs'),
                'view_mode': 'form',
                'res_model': self.res_model,
                'res_id': int(self.res_id),
                'type': 'ir.actions.act_window',
                'target': 'current'
            }
            return action
        elif self.action_type == 'read' and self.res_url:
            action = {
                'type': 'ir.actions.act_url',
                'url': self.res_url,
                'target': 'new'
            }
            return action
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': 'You can not able to view deleted record',
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }


class UserAuditLogs(models.Model):
    _name = 'user.audit.logs'
    _description = "User Logs"

    name = fields.Char(string="Title", required=True)
    previous_value = fields.Char(string="Previous Value")
    new_value = fields.Char(string="New Value")
    operation_type = fields.Selection([('new', "New Add"), ('update', "Update"), ('remove', "Removed")])
    user_audit_id = fields.Many2one('user.audit', string="User Audit")


class UserSignInDetails(models.Model):
    """User Sign In Details"""
    _name = 'user.sign.in.details'
    _description = __doc__
    _order = 'id desc'

    name = fields.Char(string='Sequence', readonly=True, copy=False)

    user_id = fields.Many2one('res.users', string='User')
    # Address
    city = fields.Char('City')
    region = fields.Char('Region')
    country = fields.Char('Country')
    timezone = fields.Char('TimeZone')
    postal_code = fields.Char(string="Postal Code")
    latitude = fields.Char(string="Latitude")
    longitude = fields.Char(string="Longitude")
    active = fields.Boolean()
    # sign-in sign-out
    logged_datetime = fields.Datetime(string='Logged Datetime')
    logout_datetime = fields.Datetime(string='Logout Datetime')
    last_active_time = fields.Datetime(string='Last Active Time')
    # technical details
    ip_address = fields.Char(string='IP Address')
    platform = fields.Selection(
        [('Windows', "Windows"), ('Linux', "Linux"), ('Mac OS', "Mac OS"), ('Android', "Android"),
         ('iOS', "iOS"), ('Other', "Other")],
        string='Operating System')
    other_platform = fields.Char(string='Other Operating System')
    platform_version = fields.Char(string='OS Version')
    is_bot = fields.Boolean()
    browser = fields.Selection([('Safari', "Safari"), ('Chrome', "Chrome"), ('Firefox', "Firefox"), ('Opera', "Opera"),
                                ('ChromiumEdge', "Edge"),
                                ('Other', "Other")], string='Browser')
    other_browser = fields.Char(string="Other Browser")
    browser_version = fields.Char(string='Browser Version')
    isp = fields.Char(string='ISP Providers')
    is_anonymous = fields.Boolean(string="Anonymous User")
    # Odoo session
    session = fields.Char(string='Session ID', readonly=True, store=True)
    # Status
    status = fields.Selection([('active', 'Active'), ('inactive', 'Terminated')], string='Status')

    def session_info(self):
        pass

    def action_view_user_logs(self):
        action = {
            'name': _('Activity Logs'),
            'view_mode': 'tree,form',
            'res_model': 'user.audit',
            'type': 'ir.actions.act_window',
            'domain': [('user_session_id', '=', self.id)],
            'target': 'current'
        }
        return action

    def terminate_user_active_session(self):
        for rec in self:
            session_obj = http.root.session_store
            session_id = session_obj.get(rec.session)
            if session_id.db and session_id.uid == rec.user_id.id and session_id.sid == rec.session:
                session_obj.delete(session_id)
            rec.sudo().write({'status': 'inactive', 'active': False, 'logout_datetime': datetime.now()})

    def action_gmap_location(self):
        if not self.latitude or not self.longitude:
            raise ValidationError(_("Location coordinates required"))
        http_url = 'https://maps.google.com/maps?q=loc:' + self.latitude + "," + self.longitude
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': http_url,
        }

    def unlink(self):
        for rec in self:
            ir_model = request.params['model']
            if rec.user_id.id == self.env.user.id and ir_model != 'base.module.uninstall':
                raise UserError(_("you can't delete your own session"))
            rec.terminate_user_active_session()
        return super(UserSignInDetails, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'user.sign.in.details') or 'New'
        res = super(UserSignInDetails, self).create(vals_list)
        is_login_alert = self.env['ir.config_parameter'].get_param('tk_security_master.login_alert')
        if is_login_alert:
            tmpl_id = self.env.ref('tk_security_master.login_user_alert_template', raise_if_not_found=False)
            if res and tmpl_id:
                tmpl_id.sudo().send_mail(res.id, force_send=True)
        return res

    @api.model
    def terminate_inactive_session_cron(self):
        config_param = self.env['ir.config_parameter'].sudo()
        auto_terminate = config_param.get_param('tk_security_master.auto_terminate_session')

        if not auto_terminate:
            return

        session_timeout = config_param.get_param('tk_security_master.session_timeout')

        if not session_timeout or int(session_timeout) <= 0:
            return

        sessions = self.env['user.sign.in.details'].sudo().search([('active', '=', True)])
        for sess in sessions:
            time_diff = datetime.now() - sess.last_active_time
            float_diff = time_diff.total_seconds() / 60
            if float_diff > int(session_timeout):
                session_obj = http.root.session_store
                session_id = session_obj.get(sess.session)
                if session_id.db and session_id.uid == sess.user_id.id and session_id.sid == sess.session:
                    session_obj.delete(session_id)
                sess.sudo().write({'status': 'inactive', 'active': False, 'logout_datetime': datetime.now()})

    @api.model
    def get_users_sessions_stats(self):
        data = []
        sessions = self.env['user.sign.in.details'].sudo().search([('active', '=', True)])
        for sess in sessions:
            if not sess.latitude or not sess.longitude or not sess.user_id:
                continue
            title = "%s\n--------------------- \nIP: %s \nBrowser: %s \nOS: %s" % (
                sess.user_id.name, sess.ip_address, sess.browser, sess.platform)
            data.append({
                'title': title,
                'latitude': sess.latitude,
                'longitude': sess.longitude,
            })
        return data

    @api.model
    def get_browser_wise_session_stats(self):
        os_counts = {
            'windows': self.get_os_wise_session_counts('Windows'),
            'linux': self.get_os_wise_session_counts('Linux'),
            'mac': self.get_os_wise_session_counts('Mac OS'),
            'android': self.get_os_wise_session_counts('Android'),
            'ios': self.get_os_wise_session_counts('iOS'),
            'other_os': self.get_os_wise_session_counts('Other'),
        }
        data = {
            'chrome': self.get_browser_wise_session_counts('Chrome'),
            'safari': self.get_browser_wise_session_counts('Safari'),
            'firefox': self.get_browser_wise_session_counts('Firefox'),
            'edge': self.get_browser_wise_session_counts('ChromiumEdge'),
            'opera': self.get_browser_wise_session_counts('Opera'),
            'other': self.get_browser_wise_session_counts(),
            'all': self.get_session_status_wise('all'),
            'active': self.get_session_status_wise('active'),
            'terminate': self.get_session_status_wise('terminate'),
            'os': os_counts,
        }
        return data

    def get_browser_wise_session_counts(self, browser_name="Other"):
        browser_counts = self.env['user.sign.in.details'].sudo().search_count(
            [('active', '=', True), ('browser', '=', browser_name)])
        return browser_counts

    def get_session_status_wise(self, sess_domain="active"):
        if sess_domain == 'active':
            domain = [('active', '=', True)]
        elif sess_domain == 'terminate':
            domain = [('active', '=', False)]
        else:
            domain = [('active', 'in', [True, False])]
        session_counts = self.env['user.sign.in.details'].sudo().search_count(domain)
        return session_counts

    def get_os_wise_session_counts(self, os_name="Other"):
        os_counts = self.env['user.sign.in.details'].sudo().search_count(
            [('active', '=', True), ('platform', '=', os_name)])
        return os_counts


class DoNotTrackModels(models.Model):
    """Do not track models"""
    _name = 'do.not.track.models'
    _description = __doc__
    _rec_name = 'res_model'

    res_model = fields.Char(string="Model", required=True)
