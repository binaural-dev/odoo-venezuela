{
    "name": "Binaural Sucursales en Inventario",
    "summary": """Agrega sucursales a los modelos relacionados con inventario.""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Hidden",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_subsidiary", "stock", "stock_account"],
    "data": [
        "security/ir_rule.xml",
        "views/stock_move.xml",
        "views/stock_move_line.xml",
        "views/stock_picking.xml",
        "views/stock_valuation_layer.xml",
        "views/stock_warehouse.xml",
    ],
    "auto_install": True,
    "license": "LGPL-3",
    "binaural": True,
}
