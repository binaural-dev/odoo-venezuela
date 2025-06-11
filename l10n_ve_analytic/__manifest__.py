{
    "name": "Venezuela - Cuentas Analiticas",
    "summary": """
       Modulo para las cuentas analiticas en la moneda alterna""",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["l10n_ve_rate", "analytic", "l10n_ve_accountant"],
    # always loaded
    "data": ["views/analytic_line_views.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
    "auto_install": True,
}
