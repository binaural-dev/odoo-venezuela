{
    "name": "Binaural Sucursales en POS",
    "summary": """Agrega el manejo de sucursales a POS""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Point Of Sale",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_subsidiary", "sh_pos_analytic_tags"],
    "auto_install": True,
}
