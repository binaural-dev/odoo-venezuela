{
    "name": "Binaural Nómina Con Contabilidad",
    "summary": """
        Modificaciones de nómina con contabilidad.
    """,
    "author": "Binauraldev",
    "license": "LGPL-3",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "version": "16.0.0.1.1",
    # any module necessary for this one to work correctly
    "depends": ["binaural_accountant", "binaural_hr_payroll"],
    "data": [
        "views/hr_department.xml",
        "views/hr_payslip.xml",
    ],
    # always loaded
    "auto_install": True,
    "binaural": True,
}
