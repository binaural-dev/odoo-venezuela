{
    "name": "Binaural Comisiones",
    "summary": """Manejo de Políticas de Comisiones""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Expense/Payroll",
    "version": "17.0.1.0.0",
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
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_actions_server.xml",
        "data/product_data.xml",
        "data/commission_policy_type.xml",
        "views/account_move_views.xml",
        "views/account_move_line_views.xml",
        "views/commission_policy_line_views.xml",
        "views/commission_policy_views.xml",
        "views/commission_policy_type_views.xml",
        "views/menuitems.xml",
        "views/res_config_settings.xml",
        "views/sale_order_views.xml",
        "views/commission_product_item_views.xml",
        "views/product_views.xml",
        "wizard/generate_commission_from_invoice_views.xml",
        "wizard/invoice_commission_summary_wizard_views.xml",
        "wizard/set_commission_order_to_invoice.xml",
    ],
    "application": True,
    "binaural":True,
}
