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
        # "account_sequence",
        # "binaural_tax",
        # "binaural_contact",
        # "binaural_rate",
        # "binaural_fiscal",
    ],
    # always loaded
    "data": [
        # "security/ir.model.access.csv",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
