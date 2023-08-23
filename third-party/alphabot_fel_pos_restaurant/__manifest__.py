# -*- coding: utf-8 -*-
{
    "name": "Alphabot FEL POS Restaurant",
    'summary': 'Factura electrónica para el POS restaurant',
    'description': 'Factura electrónica para el POS restaurant',

    'author': 'AlphaPos',
    'website': 'http://alphapos.biz',
    "support": "info@alphapos.biz",
    "license": "Other proprietary",
    'sequence': 10,
    'category': 'Point of Sale',
    'version': '0.15.22.8.18',
    'depends': ['base','account','point_of_sale','alphabot_fel_base','pos_restaurant'],
    'data': [
    ],
    'assets': {
        'point_of_sale.assets': [
            'alphabot_fel_pos_restaurant/static/src/js/*',
            'alphabot_fel_pos_restaurant/static/src/xml/*',
        ],
        'web.assets_qweb': [
        ],
    },
    'installable': True,
    'application': True,

    'images': ['static/description/logo.png'],
}
