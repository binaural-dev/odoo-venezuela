# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import http, models, fields, api


class ResUsers(models.Model):
    _inherit = "res.users"
    # session details
    user_session_ids = fields.One2many('user.sign.in.details', 'user_id', string="Sessions")
    # logs details
    tu_read_logs = fields.Boolean(string="Read Logs ?", default=True)
    tu_create_logs = fields.Boolean(string="Create Logs ?", default=True)
    tu_update_logs = fields.Boolean(string="Update Logs ?", default=True)
    tu_delete_logs = fields.Boolean(string="Delete Logs ?", default=True)
    # password expiry settings
    pwd_expire = fields.Boolean(string="Is Password Expired ?")
    pwd_update_datetime = fields.Datetime(string="Last Update Datetime", default=fields.Datetime.now)
    pwd_expire_date = fields.Date(string="Password Expiry Date")

    def terminate_user_active_sessions(self):
        for rec in self.user_session_ids.filtered(lambda act_sess: act_sess.active):
            session_obj = http.root.session_store
            session_id = session_obj.get(rec.session)
            if session_id.db and session_id.uid == rec.user_id.id and session_id.sid == rec.session:
                session_obj.delete(session_id)
            rec.sudo().write({'status': 'inactive', 'active': False, 'logout_datetime': datetime.now()})

    @api.model_create_multi
    def create(self, vals_list):
        res_users = super(ResUsers, self).create(vals_list)
        config_param = self.env['ir.config_parameter'].sudo()
        # pwd settings
        pwd_expire = config_param.get_param('tk_security_master.pwd_expire_policy')
        if not pwd_expire:
            return res_users
        # pwd updates
        pwd_expire_days = config_param.get_param('tk_security_master.pwd_expire_days')
        for usr in res_users:
            usr.sudo().pwd_expire_date = datetime.now() + relativedelta(days=int(pwd_expire_days))
        return res_users

    def write(self, vals):
        rec = super(ResUsers, self).write(vals)
        config_param = self.env['ir.config_parameter'].sudo()
        if vals.get('password'):
            vals = {'pwd_update_datetime': datetime.now(), 'pwd_expire': False}
            pwd_expire = config_param.get_param('tk_security_master.pwd_expire_policy')
            if pwd_expire:
                pwd_expire_days = config_param.get_param('tk_security_master.pwd_expire_days')
                vals['pwd_expire_date'] = datetime.now() + relativedelta(days=int(pwd_expire_days))
            self.sudo().write(vals)
        return rec

    @api.model
    def check_users_pwd_expire_status(self):
        config_param = self.env['ir.config_parameter'].sudo()
        pwd_expire = config_param.get_param('tk_security_master.pwd_expire_policy')
        if not pwd_expire:
            return

        res_users = self.env['res.users'].sudo().search([('active', '=', True)])
        for usr in res_users:
            if usr.has_group('base.group_system'):
                continue

            if usr.pwd_expire_date == date.today():
                usr.write({'pwd_expire': True})

            if (usr.pwd_expire_date + relativedelta(days=7)) == date.today():
                template = self.env.ref('tk_security_master.pwd_expire_warning_notification_users_seven_days')
                template.send_mail(usr.id, force_send=True)

            if (usr.pwd_expire_date + relativedelta(days=1)) == date.today():
                template = self.env.ref('tk_security_master.pwd_expire_warning_notification_users_one_day')
                template.send_mail(usr.id, force_send=True)
        return


class ChangePwdUsr(models.TransientModel):
    _inherit = 'change.password.user'

    def change_password_button(self):
        config_param = self.env['ir.config_parameter'].sudo()
        rec = super(ChangePwdUsr, self).change_password_button()
        pwd_expire = config_param.get_param('tk_security_master.pwd_expire_policy')
        vals = {'pwd_update_datetime': datetime.now(), 'pwd_expire': False}
        if pwd_expire:
            pwd_expire_days = config_param.get_param('tk_security_master.pwd_expire_days')
            vals['pwd_expire_date'] = datetime.now() + relativedelta(days=int(pwd_expire_days))
        # update pwd settings
        self.user_id.sudo().write(vals)
        return rec
