{
    "name": "Binaural Sucursales en POS",
    "summary": """Agrega el manejo de sucursales a POS""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Point Of Sale",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_subsidiary", "sh_pos_analytic_tags", "pos_sale"],
    "data": [
        "security/ir_rule.xml",
        "views/pos_order_report.xml",
        "views/pos_order.xml",
        "views/res_config_settings.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_subsidiary_pos/static/src/js/**/*.js",
        ],
    },
    "auto_install": True,
    "license": "LGPL-3",
    "binaural": True,
}
