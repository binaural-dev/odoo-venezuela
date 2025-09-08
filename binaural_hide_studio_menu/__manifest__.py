# -*- coding: utf-8 -*-

{
    'name': 'Binaural Blockear botton odoo studio',
    'version': '17.0.0.0.1',
    'summary': 'This module is for block the button odoo studio based on a group.',
    'license': 'LGPL-3',
    'author': 'Binauraldev',
    'website': 'https://www.binauraldev.com',
    'category': 'Services',
    'company': 'Binaural.ca',
    'maintainer': 'Binaural.ca',
    'depends': ['web','web_studio'],
    'data': [
        'security/groups.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'binaural_hide_studio_menu/static/src/js/form_arch_parser.js',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}