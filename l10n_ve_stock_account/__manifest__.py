# -*- coding: utf-8 -*-
{
    "name": "Venezuela - Stock Account",
    "summary": """
        Stock Accoun for Venezuela Localization
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock Account",
    "version": "16.0.1.0.1",
    "depends": [
        "l10n_ve_stock",
        "l10n_ve_accountant",
        "stock_move_invoice",
    ],
    "data": [
        
        "data/ir_sequence.xml",

        "views/account_move_views.xml",
        "views/stock_picking_guide_dispatch_views.xml",
        "views/stock_picking_views.xml",
        "views/menuitem_views.xml",
        
    ],
    "application": True,
    'auto_install': True,
    "binaural": True,
}
