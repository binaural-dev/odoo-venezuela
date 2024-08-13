{
    "name": "Binaural Fiscal",
    "summary": """
        Módulo para obtener campo fiscal en el diario
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_accountant", "account"],
    # always loaded
    "data": [
        "security/binaural_fiscal_groups.xml",
        "views/account_journal.xml",
        "views/account_move.xml",
    ],
    "binaural": True,
}
