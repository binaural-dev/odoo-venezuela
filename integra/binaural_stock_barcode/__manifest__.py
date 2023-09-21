{
    "name": "Binaural Codigo de barras",
    "summary": """
        Modulo para validaciones en los Codigo de barras
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.1",
    "depends": ["stock", "barcodes", "stock_barcode", "hr", "binaural_stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/barcode_rule.xml",
        "views/stock_picking_views.xml",
        "views/hr_employee_views.xml",
        "views/stock_picking_type_views.xml",
        "views/stock_picking_cart_views.xml",
        "wizard/operation_supervisor_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "binaural_stock_barcode/static/src/js/*.js",
            "binaural_stock_barcode/static/src/xml/*.xml",
            "binaural_stock_barcode/static/src/css/*.css",
        ]
    },
}
