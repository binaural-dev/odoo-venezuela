{
    "name": "Binaural Ganaderia",
    "summary": "Modulo para información de Ganaderia",
    "version": "16.0.0.0.0",
    "category": "Stock",
    "license": "LGPL-3",
    "author": "BinauralDev",
    'data': [
        'security/ir.model.access.csv',
        'data/res_groups.xml',
        'views/stock_lot_views.xml',
        'views/stock_lot_race_views.xml',
        'views/res_partner_views.xml',
        'views/stock_lot_breeder_views.xml',
        
    ],
    "depends": [
        "stock",
        "account",
    ],
    'images': ['static/description/icon.png'],
    "installable": True,
    "application": True,
}