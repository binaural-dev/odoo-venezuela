{
    "name": "Binaural Sucursales/IGTF",
    "summary": """
        Modulo para agregar sucursales (cuentas analiticas) a los asientos adicionales de IGTF.
    """,
    "author": "Binauraldev",
    "license": "LGPL-3",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Uncategorized",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_subsidiary", "binaural_igtf"],
    # always loaded
    "data": [],
    "auto_install": True,
    "binaural": True,
}
