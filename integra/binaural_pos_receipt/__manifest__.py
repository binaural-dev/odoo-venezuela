{
    "name": "Binaural Recibos POS",
    "summary": """
    Formato de Recibos en POS
    """,
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Point of Sale",
    "version": "16.0.0.1.3",
    "depends": ["binaural_pos", "point_of_sale"],
    "data": [],
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_receipt/static/src/scss/pos.scss",
            "binaural_pos_receipt/static/src/css/receipt.css",
            "binaural_pos_receipt/static/src/js/**/*.js",
            "binaural_pos_receipt/static/src/xml/**/*.xml",
        ]
    },
    "license": "LGPL-3",
    "binaural": True,
}
