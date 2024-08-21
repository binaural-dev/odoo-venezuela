{
    "name": "Binaural POS Descuentos",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "summary": "Binaural POS Descuentos",
    "sequence": "1",
    "license": "LGPL-3",
    "author": "Binaural.dev",
    "support": "contacto@binaural.dev",
    "depends": ["point_of_sale", "pos_discount", "binaural_pos"],
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
    "binaural": True,
}
