# -*- coding: utf-8 -*-
{
    'name': 'Alphabot FEL Base',
    'summary': "Alphabot para facturación electrónica Panamá",
    'description': 'Alphabot para facturación electrónica Panamá',
    'category': 'Invoicing',
    'author': 'AlphaPos',
    'website': 'http://alphapos.biz',
    "support": "info@alphapos.biz",
    "license": "Other proprietary",
    'sequence': 10,     
    'version': '0.16.23.05.12',
    'depends': ['base','account','alphabot_licencia','alphabot_fel_localization','alphabot_fel_settings'],
    'data': [
        'data/alphabot_seq.xml',
        'data/automatic_fel.xml',
        'security/ir.model.access.csv',
        'views/menu_view.xml',
        'views/res_company_views.xml',
        'views/res_partner.xml',
        'views/fel_move_view.xml',
        'views/product_view.xml',
        'views/res_config_settings_views.xml',
    ],
    'qweb': [
     
    ],
    'installable': True,
    'application': True,
    #'image': ['static/description/alpha_logo.png'],
}