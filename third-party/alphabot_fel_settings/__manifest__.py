# -*- coding: utf-8 -*-
{
    'name': 'Alphabot FEL Settings',
    'summary': "Alphabot para facturación electrónica Panamá - Configuraciones",
    'description': 'Alphabot para facturación electrónica Panamá',
    'category': 'Invoicing',
    'author': 'AlphaPos',
    'website': 'http://alphapos.biz',
    "support": "info@alphapos.biz",
    "license": "Other proprietary",
    'sequence': 10, 
    'version': '0.15.22.6.24',
    'depends': ['base','account'],
    'data': [
        'security/ir.model.access.csv',    
        'data/values.xml',   
        'data/doctype.xml',
        'data/segmentcpbs.xml',    
        'data/familycpbs.xml',
        'data/taxrate.xml',
        'views/menu_view.xml',
    ],
    'qweb': [
    ],
    'installable': True,
    'application': False,
    #'image': ['static/description/alpha_logo.png'],
}