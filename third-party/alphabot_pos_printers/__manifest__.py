# -*- coding: utf-8 -*-
{
    "name": "AlphaPrint POS Printers",
    'summary': 'Uso de Alphabot en POS',
    'description': 'Impresoras de comandas en Windows',
    'author': 'AlphaPos',
    'website': 'http://alphapos.biz',
    "support": "info@alphapos.biz",
    "license": "Other proprietary",
    'sequence': 10,
    'version': '0.16.23.06.06',
    'depends': ['base','account','point_of_sale','pos_restaurant','alphabot_licencia'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_printers.xml',        
        ],
    'assets': {
        'point_of_sale.assets': [
            'alphabot_pos_printers/static/src/js/*',
            'alphabot_pos_printers/static/src/xml/**/*',
        ],
        'web.assets_qweb': [
        ],
    },
    'installable': True,
    'application': True,

  #  'images': ['static/description/banner.png'],
}
