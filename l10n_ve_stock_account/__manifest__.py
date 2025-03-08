{
    "name": "Venezuela - Stock Account",
    "summary": """
        Stock Accoun for Venezuela Localization
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://www.binauraldev.com",
    "category": "Stock Account",
    "version": "16.0.1.0.0",
    "depends": [
        "l10n_ve_stock",
        "l10n_ve_accountant",
        "stock_move_invoice",
    ],
    "data": [
        
        "data/ir_sequence.xml",

        "views/stock_picking_guide_dispatch_views.xml",
        "views/stock_picking_views.xml",
        "views/menuitem_views.xml",
        
    ],
    "application": True,
    'auto_install': True,
}
