{
    "name": "Binaural Sucursales/Anticipos",
    "summary": """
        Módulo para agregar la sucursal(cuenta analítica) en los asientos de anticipos
    """,
    "author": "Binauraldev",
    "license": "LGPL-3",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Accounting",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_subsidiary", "binaural_advance_payment"],
    # always loaded
    "data": [],
    "binaural": True,
}
