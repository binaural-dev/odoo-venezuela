# -*- coding: utf-8 -*-
#############################################################################
#
#    TechKhedut Inc.
#
#    Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
#    Author: TechKhedut(<https://www.techkhedut.com>)
#    Part of TechKhedut. See LICENSE file for full copyright and licensing details.
#
#############################################################################
{
    'name': "Security Master | User Login Security Master | Advanced User Audit | User Logs | User Activity Audit | Odoo Security Master | Security Dashboard | Session Management | Login Alert",
    'description': """
        - Advance Security Master
        - User Audit
        - User Activity Tracking
        - Session Management
        - Kill All Sessions
        - Advance User Login Security
        - Login Alert
        - Login Cooldown Period
        - Failed Login Ban
        - Password Expiry
        - Inactive Session Terminate
        - Maximum Number of Login Retry
    """,
    'summary': """
           Advanced Security Master for manage user activity logs, session management, inactive session terminate, password expiry, password extra layers,
     login alert, & much more.
    """,
    'version': "1.0.3",
    'author': 'TechKhedut Inc.',
    'company': 'TechKhedut Inc.',
    'maintainer': 'TechKhedut Inc.',
    'website': "https://techkhedut.com",
    'category': 'Services',
    'depends': ['base', 'mail', 'auth_signup', 'web', 'base_setup'],
    'data': [
        # Security
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        # Data
        'data/ir_cron.xml',
        'data/ir_sequence.xml',
        'data/mail_templates.xml',
        # Assets
        'views/assets.xml',
        # Views
        'views/user_session_views.xml',
        'views/do_not_track_models_views.xml',
        'views/user_audit_logs_views.xml',
        # Inherit Views
        'views/res_config_settings_views.xml',
        'views/res_users_views_inherit.xml',
        # Templates
        'views/templates/change_pwd_user.xml',
        # Menus
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # other
            'tk_security_master/static/src/xml/dashboard.xml',
            'tk_security_master/static/src/scss/style.scss',
            'tk_security_master/static/src/js/route/service.js',
            'tk_security_master/static/src/js/dashboard/dashboard.js',
        ],
        'web.assets_frontend': [
            'tk_security_master/static/src/js/other/script.js',
        ],
    },
    'external_dependencies': {
        'python': ['httpagentparser']
    },
    'images': [
        'static/description/banner.gif'
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 199,
    'currency': 'USD',
    'post_init_hook': 'post_init',
}
