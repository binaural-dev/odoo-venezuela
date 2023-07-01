# -*- coding: utf-8 -*-
{
    'name': 'Alphabot FEL localization',
    'summary': "Alphabot para facturación electrónica Panamá - Localización",
    'description': 'Alphabot para facturación electrónica Panamá',
    'author': 'AlphaPos',
    'website': 'http://alphapos.biz',
    "support": "info@alphapos.biz",
    "license": "Other proprietary",
    'sequence': 10, 
    'version': '0.16.23.05.11',
    'depends': ['base','account'],
    'data': [  
        'security/ir.model.access.csv',        
        "data/res_country_states.xml",
        "data/res_country_districts.xml",       
        "data/res_country_municipalities.xml", 
        'views/menu_view.xml',
        'views/res_company_view.xml',
        'views/res_partner_view.xml',
    ],
    'qweb': [
    ],
    'installable': True,
    'application': False,
    #'image': ['static/description/alpha_logo.png'],
}