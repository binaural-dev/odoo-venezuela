{
    "name": "Binaural Sucursales para anticipos con IGTF",
    "summary": """Agrega las sucursales (cuentas analíticas) a los anticipos con IGTF""",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "author": "Binauraldev",
    "category": "Accounting",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    # any module necessary for this one to work correctly
    "depends": ["binaural_subsidiary", "binaural_advance_payment_igtf"],
    # always loaded
    "data": [
    ],
    "auto_install": True,
    "binaural": True,
}
