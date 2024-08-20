{
    "name": "Binaural Cierre Fiscal Con Sucursales",
    "summary": """Crear asientos de cierre fiscal por sucursal""",
    "author": "Binaural",
    "license": "LGPL-3",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Technical",
    "version": "16.0.1.0.1",
    # any module necessary for this one to work correctly
    "depends": ["binaural_account_fiscalyear_closing","binaural_subsidiary"],
    # always loaded
    "auto_install": True,
    "binaural": True,
}
