{
    "name": "Binaural POS - APP Movil",
    "summary": """
       Modulo para Localizacion Venezolana en POS y Ventas""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "pos_sale",
        "point_of_sale",
        "binaural_pos",
        "binaural_pos_sale",
        "binaural_mobile"
    ],
    # always loaded
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_mobile/static/src/js/*.js",
        ],
    },
    "binaural": True,
}
