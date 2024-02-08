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
    "version": "16.0.1.0.7",
    # any module necessary for this one to work correctly
    "depends": [
        "account",
        "product",
        "binaural_accountant",
        "binaural_brand",
        "binaural_sale",
        "binaural_seller",
        "binaural_invoice",
    ],
    # always loaded
    "data": [
        "data/ir_actions_server.xml",
        "data/product_data.xml",
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/commission_policy_line_views.xml",
        "views/commission_policy_views.xml",
        "views/res_config_settings.xml",
        "views/menuitems.xml",
        "views/res_config_settings.xml",
        "views/sale_order_views.xml",
        "views/commission_product_item_views.xml",
        "views/product_views.xml",
        "wizard/generate_commission_from_invoice_views.xml",
    ],
    "application": True,
}
