{
    "name": "Binaural POS Vendedores",
    "summary": """
       Modulo para POS Vendedores""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.0.10",
    # any module necessary for this one to work correctly
    "depends": ["binaural_seller","binaural_pos_sale","binaural_pos","point_of_sale","pos_hr"],
    # always loaded
    "data": [
        "views/pos_order.xml",
        "views/res_config_settings_views.xml",
    ],
    "images": ["static/description/icon.png"],
    'auto_install': True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_seller/static/src/js/*.js",
            "binaural_pos_seller/static/src/xml/*.xml",
        ]
    },
    "binaural": True,
}
