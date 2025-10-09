# -*- coding: utf-8 -*-

{
    'name': 'Binaural Descuento en compras',
    'version': '1.0.0',
    'category': 'Purchase',
    'summary': 'Descuento global en órdenes de compra (similar al descuento en ventas Odoo 17.0)',
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Purchase/Purchase",
    "version": "17.0.0.0.1",
    'depends': ['l10n_ve_purchase','l10n_ve_invoice'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/purchase_order_discount_views.xml',
        'views/purchase_order_view.xml',
        'views/res_config_settings.xml',
    ],
    'installable': True,
    'auto_install': False,
}
