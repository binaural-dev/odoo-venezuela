{
    "name": "Binaural Codigo de barras",
    "summary": """
        Modulo para validaciones en los Codigo de barras
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0",
    "depends": ["stock", "stock_barcode"],
    "data": ["views/res_config_settings_views.xml"],
    "assets": {
        "web.assets_backend": [
            "binaural_stock_barcode/static/src/js/*.js",
        ]
    },
}
