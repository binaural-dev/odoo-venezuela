{
    "name": "Binaural Codigo de barras",
    "summary": """
        Modulo para validaciones en los Codigo de barras
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "17.0.1.0.0",
    "depends": ["stock", "barcodes", "stock_barcode", "hr", "binaural_stock"],
    "data": [
        "security/ir.model.access.csv",
        "security/res_groups.xml",
        "data/barcode_rule.xml",
        "data/report_paperformat.xml",
        "report/packaging_picking_template.xml",
        "views/res_config_settings_views.xml",
        "views/stock_picking_views.xml",
        "views/hr_employee_views.xml",
        "views/stock_picking_type_views.xml",
        "views/action_print_barcode_cart.xml",
        "views/stock_picking_cart_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_location_views.xml",
        "wizard/operation_supervisor_views.xml",
        "wizard/stock_picking_incomplete.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "binaural_stock_barcode/static/src/**/**",
        ]
    },
    "application": True,
}
