{
    "name": "Binaural Fiscal",
    "summary": """
        Módulo para obtener campo fiscal en el diario
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.0.0.3",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_accountant", "account"],
    # always loaded
    "data": [
        "security/binaural_fiscal_groups.xml",
        "security/ir_rule.xml",
        "security/ir.model.access.csv",
        "views/account_journal.xml",
        "views/account_move.xml",
        "views/menu_item.xml",
    ],
}
