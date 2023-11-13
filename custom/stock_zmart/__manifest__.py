{
    "name": "Zmart Stock",
    "summary": """
       Modulo para  personalizar campo en modulo de inventario""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Stock",
    "version": "16.0.0.10",
    "depends": [
        "binaural_sale",
        "binaural_stock",
        "delivery",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/paperformat.xml",
        "data/ir_sequence.xml",
        "data/res_group.xml",
        "views/ir_sequence.xml",
        "report/picking_order_report.xml",
        "report/report_albaran.xml",
        "views/stock_picking.xml",
        "views/res_config_settings_views.xml",
        "views/menu.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
