{
    "name": "Binaural POS con IGTF",
    "summary": "Modulo para calculos del impuesto IGTF (Impuesto a las grandes transacciones financieras) en POS",
    "license": "AGPL-3",
    "description": "Modulo para calculos del impuesto IGTF (Impuesto a las grandes transacciones financieras) en POS",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "16.0.2.0.2",
    "depends": ["base", "binaural_pos", "binaural_base_igtf"],
    "data": ["views/pos_payment_method.xml"],
    "images": ["static/description/icon.png"],
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_igtf/static/src/js/*.js",
            "binaural_pos_igtf/static/src/xml/*.xml",
            "binaural_pos_igtf/static/src/css/*.css",
        ],
    },
    "application": True,
    "binaural": True,
}
