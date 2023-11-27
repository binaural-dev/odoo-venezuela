{
    "name": "Binaural Retenciones/Sucursales",
    "summary": """
        Modulo para agregar sucursales (cuentas analiticas) a los pagos de retenciones.
    """,
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Uncategorized",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_payment_extension", "binaural_subsidiary"],
    # always loaded
    "data": [
        "report/retention_line_report_views.xml",
        "views/analytic_account.xml",
    ],
    "auto_install": True,
}
