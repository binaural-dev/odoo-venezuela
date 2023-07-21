# -*- coding: utf-8 -*-
{
    'name': 'Alphabot FEL Digifact',
    'summary': "Interfaz para FEL Digifact",
    'description': 'Interfaz para FEL Digifact',
    'category': 'Invoicing',
    'author': 'AlphaPos',
    'website': 'http://alphapos.biz',
    "support": "info@alphapos.biz",
    "license": "Other proprietary",
    'sequence': 10,     
    'version': '0.16.23.05.26',
    'depends': ['alphabot_fel_base'],
    'data': [
        'security/ir.model.access.csv',
        # 'views/info_view.xml',
        'views/res_company_views.xml',
        'views/res_partner.xml',
        'views/menu_view.xml',
        'views/fel_branch.xml',
        'views/fel_move_view.xml',
    ],
    'qweb': [
    ],
    'installable': True,
    'application': True,
}


