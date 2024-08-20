{
    "name": "Binaural Comisiones en POS",
    "summary": """
       Modulo para Localizacion Venezolana en POS""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.0.5",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale", "binaural_pos", "binaural_commissions"],
    # always loaded
    "data": [
        "wizards/set_commission_order_to_invoice.xml",
        "data/ir_actions_server.xml",
        "views/pos_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_commissions/static/src/js/*.js",
            # "binaural_pos/static/src/xml/*.xml",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
}
