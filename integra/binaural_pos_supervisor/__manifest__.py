{
    "name": "Binaural Pos Supervisor",
    "summary": """
       Modulo para Localizacion Venezolana en POS que implementa el flujo de supervisores""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.0.1",
    "depends": ["binaural_pos", "pos_sale_product_configurator"],
    # "data": ["views/res_config_settings.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_supervisor/static/src/js/*.js",
            "binaural_pos_supervisor/static/src/xml/*.xml",
            "binaural_pos_supervisor/static/src/css/*.css",
            (
                "replace",
                "pos_sale_product_configurator/static/src/js/models.js",
                "binaural_pos_supervisor/static/src/js/models.js",
            ),
        ],
    },
}
