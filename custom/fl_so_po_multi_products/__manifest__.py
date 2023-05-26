# -*- coding: utf-8 -*-
{
    'name': 'SO & PO Multi Product Selection',
    'version': '16.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Sale order and Purchase order Multiple Product Selection',
    'description': """
        This module provide select multiple products
        Features includes managing
            * allow to choose multiple products at once in sale order
            * allow to choose multiple products at once in purchase order
    """,
    'sequence': 1,
    'author': 'Futurelens',
    'website': 'http://thefuturelens.com',
    'depends': ['base', 'product', 'sale_management', 'purchase'],
    'data': [
        'wizard/select_products_wizard_view.xml',
        'views/sale_views.xml',
        'views/purchase_views.xml',
        'security/ir.model.access.csv'
    ],
    'images': [
        'static/description/so_po_multi_product_banner.png',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
