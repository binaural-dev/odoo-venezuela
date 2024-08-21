{
    "name": "Binaural Inspeccion Fiscal",
    "summary": """
        Módulo para crear el usuario de inspeccion fiscal
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "web",
        "account_accountant",
        "account",
        "account_reports",
        "binaural_account_reports",
        "binaural_payment_extension",
        "binaural_invoice",
    ],
    # always loaded
    "data": [
        "security/binaural_fiscal_groups.xml",
        "security/ir_rule.xml",
        "security/ir.model.access.csv",
        # "data/res_users.xml",
        "views/menu_item.xml",
        "views/account_move.xml",
        "views/account_payment.xml",
        "views/account_retention.xml",
    ],
    "post_init_hook": "create_res_users_fiscal",
    "uninstall_hook": "inspector_uninstall_hook",
    "binaural": True,
}
