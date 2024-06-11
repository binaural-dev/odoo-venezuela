{
    "name": "Binaural Fiscal",
    "summary": """
        Módulo para obtener campo fiscal en el diario
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.1.0.5",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_accountant", "account","sale", "sales_team",],
    # always loaded
    "data": [
        "security/binaural_fiscal_groups.xml",
        "security/security_group.xml",
        "views/account_journal.xml",
        "views/account_move.xml",
    ],
    "binaural": True,
}
