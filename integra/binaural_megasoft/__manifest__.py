{
    "name": "Binaural Megasoft",
    "summary": """
        Megasoft, cambios.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "16.0.1.0.2",
    "depends": [
        "base",
        "point_of_sale",
        "pos_sale",
        "iot",
        "pos_iot",
        "binaural_iot_mf",
        "binaural_pos",
        "binaural_pos_mf",
        "web",
        "binaural_rate",
    ],
    "data": [
        "views/pos_config.xml",
        "views/res_config_settings.xml",
        "views/pos_payment_method.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_megasoft/static/src/js/*.js",
            "binaural_megasoft/static/src/xml/*.xml",
            "binaural_megasoft/static/src/css/*.css",
        ],
    },
    "binaural": True,
}
