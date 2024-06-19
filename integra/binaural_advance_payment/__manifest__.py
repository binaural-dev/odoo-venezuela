{
    "name": "Binaural Anticipos",
    "summary": """
       Modulo para Anticipos en contabilidad Venezolana """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Igtf",
    "version": "16.3",
    # any module necessary for this one to work correctly
    "depends": ["base", "binaural_accountant", "binaural_tax", "binaural_rate", "binaural_fiscal"],
    # always loaded
    "data": [
        "views/res_config_settings.xml",
        "views/account_payment.xml",
        "views/account_move.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural":True,
}
