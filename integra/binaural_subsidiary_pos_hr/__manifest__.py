{
    "name": "Binaural Sucursales en POS HR",
    "summary": """Agrega el manejo de sucursales a POS HR""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Point Of Sale",
    "version": "16.0.0.0.3",
    "depends": ["binaural_subsidiary_pos", "binaural_pos_hr"],
    "data": [

    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_subsidiary_pos_hr/static/src/js/*.js",
        ],
    },
    "auto_install": True,
    "license": "LGPL-3",
    "binaural": True,
}
