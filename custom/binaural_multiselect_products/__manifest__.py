# -*- coding: utf-8 -*-
{
    'name': 'Binaural Multi-Selector De Productos',
    'version': '16.0',
    'category': 'Sales/Sales',
    'summary': 'Custom Multiple Product Selection based on fl_so_po_multi_products',
    'description': """
        This module provide select multiple products, 
        based on fl_so_po_multi_products
    """,
    'author': 'BinauralDev C.A',
    'website': 'https://binauraldev.com/',
    'depends': ['fl_so_po_multi_products',],
    'data': [
        'views/sale_views.xml',
        'views/purchase_views.xml',
        'views/product_product.xml',
    ],
    "images": ["static/description/icon.png"],
    'application': True,
    'license': 'LGPL-3',
}
