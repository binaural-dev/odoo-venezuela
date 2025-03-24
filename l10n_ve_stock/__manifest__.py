# -*- coding: utf-8 -*-
{
    "name": "Venezuela - Inventario",
    "summary": """
        Inventario para la localización en Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "17.0.0.0.0",
    "depends": [
        "stock",
        "l10n_ve_tax",
        "product",
        "l10n_ve_rate",
        "stock_delivery",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security_l10n_ve_stock.xml",
        "security/l10n_ve_stock_groups.xml",
        "data/inventory_valuation_paperformat.xml",
        "data/ir_actions_server.xml",
        "report/packaging_picking_template.xml",
        "report/inventory_valuation_report.xml",
        "views/product_category_views.xml",
        "views/products_views.xml",
        "views/res_config_settings_views.xml",
        "views/stock_quant_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_location_views.xml",
        "wizard/stock_quantity_history.xml",
    ],
    "application": True,
}
