{
    "name": "Binaural Contabilidad",
    "summary": """
       Modulo para contabilidad Venezolana """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "16.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "account_accountant",
        "account_sequence",
        "binaural_tax",
        "binaural_contact",
        "binaural_rate",
        "binaural_fiscal",
    ],
    # always loaded
    "data": [
        "data/account_data.xml",
        "views/account_invoice_report.xml",
        "views/account_move.xml",
        "views/account_payment.xml",
        "wizard/account_payment_register.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
