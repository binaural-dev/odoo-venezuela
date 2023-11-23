{
    "name": "Binaural Cierre Fiscal",
    "summary": """
       Modulo para Cierre Fiscal """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "0.0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        # "web",
        "account_accountant",
        "account",
        "binaural_payment_extension"
        # "account_sequence",
        # "binaural_tax",
        # "binaural_contact",
        # "binaural_rate",
        # "binaural_fiscal",
    ],
    # always loaded
    "data": [
        "security/account_fiscalyear_closing_security.xml",
        "security/ir.model.access.csv",
        "views/account_fiscalyear_closing_views.xml",
        "views/account_fiscalyear_closing_template_views.xml",
        "views/account_move_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
