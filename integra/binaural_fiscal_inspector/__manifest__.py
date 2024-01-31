{
    "name": "Binaural Inspeccion Fiscal",
    "summary": """
        Módulo para crear el usuario de inspeccion fiscal
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.0.1.4",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_accountant", "account","account_reports","binaural_account_reports"],
    # always loaded
    "data": [
        "security/binaural_fiscal_groups.xml",
        "security/ir_rule.xml",
        "security/ir.model.access.csv",
        "data/res_users.xml",
        "views/menu_item.xml",
    ],
    'post_init_hook': "create_res_users_fiscal",
}
