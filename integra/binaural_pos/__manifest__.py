{
    "name": "Binaural POS",
    "summary": """
       Modulo para Localizacion Venezolana en POS""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale", "binaural_rate","binaural_contact"],
    # always loaded
    "data": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos/static/src/js/*.js",
            "binaural_pos/static/src/xml/*.xml",
            "binaural_pos/static/src/css/*.css",
        ],
    },
}
