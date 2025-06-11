{
    "name": "Venezuela - Cierre Fiscal",
    "summary": """
        Procesos de cierre de fin de año fiscal en Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.0.0.0",
    "depends": [
        "account",
        "l10n_ve_contact",
        "l10n_ve_rate",
    ],
    "data": [
        "security/account_fiscalyear_closing_security.xml",
        "views/account_fiscalyear_closing_views.xml",
        "views/account_fiscalyear_closing_template_views.xml",
        "views/account_move_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
