# -*- coding: utf-8 -*-
{
    "name": "Binaural Comisiones",
    "summary": """Manejo de Políticas de Comisiones""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Expense/Payroll",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": ["account", "binaural_brand", "binaural_sale"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/commission_policy_views.xml",
        "views/commission_policy_line_views.xml",
        "views/menuitems.xml",
        "views/res_config_settings.xml"
    ],
    "application": False,
}
