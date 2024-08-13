{
    "name": "Binaural Inventario y Contabilidad",
    "summary": """Agrega campos de litros por producto en Stock.Accountant cuando es Contabilidad.""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Hidden",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "account",
        "stock"
    ],
    "data": [
        # "security/ir_rule.xml",
        "views/account_move.xml",
    ],
    "auto_install": True,
}
