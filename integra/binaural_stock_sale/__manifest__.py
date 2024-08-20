{
    "name": "Binaural Inventario y Ventas",
    "summary": """Agrega Validacion de  warehouse relacionados en ventas.""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Hidden",
    "license": "LGPL-3",
    "version": "16.0.0.0.6",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_stock",
        "binaural_sale",
        "stock",
    ],
    "data": [
        # "security/ir_rule.xml",
        "views/stock_picking.xml",
        "views/sale_order.xml"
    ],
    "auto_install": True,
    "binaural": True,
}
