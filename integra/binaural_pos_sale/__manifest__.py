{
    "name": "Binaural POS Sale",
    "summary": """
       Modulo para Localizacion Venezolana en POS y Ventas""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.0.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale", "pos_sale"],
    # always loaded
    "data": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_sale/static/src/js/*.js",
            "binaural_pos_sale/static/src/xml/*.xml",
            "binaural_pos_sale/static/src/css/*.css",
        ],
    },
}
