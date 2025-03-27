# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SecurityMasterConfig(models.TransientModel):
    _inherit = 'res.config.settings'

    login_alert = fields.Boolean(string='Is Login Alert?',
                                 config_parameter='tk_security_master.login_alert')
    auto_session_terminate = fields.Boolean(string='Auto terminate inactive session ?', default=False,
                                            config_parameter='tk_security_master.auto_terminate_session')
    session_timeout = fields.Integer(string='Session Timeout', default=90,
                                     config_parameter='tk_security_master.session_timeout')
    login_cooldown = fields.Integer(string='Login CoolDown', default=60,
                                    config_parameter='base.login_cooldown_duration')
    login_max_attempts = fields.Integer(string='Login Max Attempts', default=10,
                                        config_parameter='base.login_cooldown_after')

    pwd_expire = fields.Boolean(string='Password Expire Policy', default=False,
                                config_parameter='tk_security_master.pwd_expire_policy')
    pwd_expire_days = fields.Integer(string='Expiry Days', default=30,
                                     config_parameter='tk_security_master.pwd_expire_days')
    enable_auto_delete = fields.Boolean(string='Is Enable Auto delete tag?', default=False,
                                        config_parameter='tk_security_master.enable_auto_delete')
    create_log = fields.Boolean(string='Create', default=False, config_parameter='tk_security_master.create_log')
    read_log = fields.Boolean(string='Read', default=False, config_parameter='tk_security_master.read_log')
    update_log = fields.Boolean(string='Update', default=False, config_parameter='tk_security_master.update_log')
    delete_log = fields.Boolean(string='Delete', default=False, config_parameter='tk_security_master.delete_log')
    auto_delete_log_days = fields.Integer('After How many days.', default=30,
                                          config_parameter='tk_security_master.auto_delete_log_days')

    @api.constrains('pwd_expire_days')
    def _validate_pwd_input(self):
        if self.pwd_expire and not self.pwd_expire_days:
            raise UserError(_('Expiry Days cannot be less than 0.'))

    @api.model_create_multi
    def create(self, vals_list):
        rec = super(SecurityMasterConfig, self).create(vals_list)
        res_users = self.env['res.users'].sudo().search([])
        res_config = self.env['res.config.settings'].sudo().search([])
        new_rec = res_config[len(res_config) - 1]
        if not rec.pwd_expire:
            for usr in res_users:
                usr.write({'pwd_expire': False, 'pwd_expire_date': False})
        elif res_config and new_rec.pwd_expire_days != rec.pwd_expire_days:
            for usr in res_users:
                usr.write({'pwd_update_datetime': datetime.now(),
                           'pwd_expire_date': datetime.now() + relativedelta(days=rec.pwd_expire_days)})
        else:
            for usr in res_users:
                usr.write({'pwd_update_datetime': datetime.now(),
                           'pwd_expire_date': datetime.now() + relativedelta(days=rec.pwd_expire_days)})
        return rec
