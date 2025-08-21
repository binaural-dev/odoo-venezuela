{
    "name": "Venezuela - Libro de Inventario",
    "summary": """
        Módulo de libro de Inventario Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://www.binauraldev.com",
    "category": "Stock / Inventory",
    "version": "17.0.0.0.18",
    "depends": [
        "stock",
        "account",
        "product",
        "sale_stock",
        "l10n_ve_invoice",
        "binaural_foreign_report_stock_move_line"
    ],
    "data": [
        "security/ir.model.access.csv",

        "views/res_config_settings_views.xml",

        "data/transfer_reason.xml",

        "wizard/stock_book_report.xml",

        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
}
