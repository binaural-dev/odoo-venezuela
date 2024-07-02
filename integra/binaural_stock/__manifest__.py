# -*- coding: utf-8 -*-
{
    "name": "Binaural Inventario",
    "summary": """
        Modulo de localización relacionado
        al inventario.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0.16.0.8",
    "depends": ["stock","binaural_tax", "binaural_rate", "delivery", "binaural_brand"],
    "data": [
        "security/security_binaural_stock.xml",
        "security/binaural_stock_groups.xml",
        "data/inventory_valuation_paperformat.xml",
        "data/ir_actions_server.xml",
        "report/inventory_valuation_report.xml",
        "views/product_category_views.xml",
        "views/products_views.xml",
        "views/res_config_settings_views.xml",
        "views/stock_quant_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
        "wizard/stock_quantity_history.xml",
    ],
    "binaural": True,
}
