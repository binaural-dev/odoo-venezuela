{
    "name": "Binaural POS Sale",
    "summary": """
       Modulo para Localizacion Venezolana en POS y Ventas""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.2.0.3",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "point_of_sale",
        "binaural_pos",
        "pos_sale",
        "pos_sale_product_configurator",
    ],
    # always loaded
    "data": ["views/res_config_settings_views.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_sale/static/src/js/*.js",
            "binaural_pos_sale/static/src/xml/*.xml",
            "binaural_pos_sale/static/src/css/*.css",
            (
                "replace",
                "pos_sale_product_configurator/static/src/js/models.js",
                "binaural_pos_sale/static/src/js/PosSaleProductConfiguratorOrder.js",
            ),
        ],
    },
    "binaural": True,
}
