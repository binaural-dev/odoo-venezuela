{
    "name": "Binaural IGTF",
    "summary": """
       Modulo para IGTF en contabilidad Venezolana """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Igtf",
    "version": "1.9",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "account_accountant", "binaural_tax", "binaural_rate", "binaural_fiscal", "binaural_base_igtf"],
    # always loaded
    "data": [
    "views/account_journal.xml",
    "views/account_payment.xml",
    "wizard/account_payment_register.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
