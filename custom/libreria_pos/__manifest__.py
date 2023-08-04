{
    "name": "Libreria POS",
    "summary": """
       Modulo para Libreria en POS""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.2",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale"],
    # always loaded
    "data": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "libreria_pos/static/src/xml/*.xml",
            "libreria_pos/static/src/css/*.css",
        ],
    },
}
