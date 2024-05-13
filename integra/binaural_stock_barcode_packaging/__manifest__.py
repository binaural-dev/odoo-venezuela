{
    "name": "Binaural Paquetes en Código de Barras",
    "summary": """Bultos en Código de Barars""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0.1.0.1",
    "depends": ["stock_barcode", "binaural_stock"],
    "data": ["views/stock_picking_views.xml"],
    "assets": {
        "web.assets_backend": [
            "binaural_stock_barcode_packaging/static/src/**/**",
        ]
    },
    "application": True,
}
