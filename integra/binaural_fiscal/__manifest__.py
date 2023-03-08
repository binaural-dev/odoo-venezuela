{
    "name": "Binaural Fiscal",
    "summary": """
        Módulo para obtener campo fiscal en el diario
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_accountant"],
    # always loaded
    "data": [
        'views/account_journal.xml',
    ],
}
