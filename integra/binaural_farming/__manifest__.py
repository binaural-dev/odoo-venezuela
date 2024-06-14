{
    "name": "Binaural Ganaderia",
    "summary": "Modulo para información de Ganaderia",
    "version": "16.0.0.0.21",
    "category": "Stock",
    "license": "LGPL-3",
    "author": "BinauralDev",
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/res_groups.xml',
        'data/types_morphological_data.xml',
        'data/qualitative_valuation_data.xml',
        # Views
        'views/stock_lot_views.xml',
        'views/stock_lot_race_views.xml',
        'views/res_partner_views.xml',
        'views/stock_lot_breeder_views.xml',
        'views/stock_lot_qualitative_valuation_views.xml',
        'views/stock_lot_type_morphological_views.xml',
        
    ],
    "depends": [
        "stock",
        "account",
    ],
    'images': ['static/description/icon.png'],
    "installable": True,
    "application": True,
}