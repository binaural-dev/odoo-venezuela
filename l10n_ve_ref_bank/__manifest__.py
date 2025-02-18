{
    "name": "Binaural Referencias Bancarias",
    "summary": """
       Modulo para validar referencias Bancarias """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.1.0.1",
    # any module necessary for this one to work correctly
    "depends": ["l10n_ve_invoice"],
    # always loaded
    "data": [
        "views/account_journal.xml",
        "views/res_config_settings.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
