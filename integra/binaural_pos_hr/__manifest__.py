{
    "name": "Binaural POS HR",
    "version": "16.2",
    "category": "Accounting",
    "summary": "Binaural POS HR",
    "sequence": "1",
    "license": "LGPL-3",
    "author": "Binaural.dev",
    "support": "contacto@binaural.dev",
    "depends": ["binaural_pos", "binaural_pos_discount"],
    "data": [],
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_discount/static/src/js/*.js",
            "binaural_pos_discount/static/src/xml/*.xml",
            "binaural_pos_discount/static/src/css/*.css",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": True,
}
