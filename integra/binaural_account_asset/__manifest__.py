{
    "name": "Binaural Gestión de activos fijos",
    "summary": """
        Módulo con modificaciones para la gestión de activos fijos en Venezuela.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_asset", "binaural_accountant"],
    # always loaded
    "data": [
        "views/account_asset.xml",
    ],
    "binaural":True,
}
