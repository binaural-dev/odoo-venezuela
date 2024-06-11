{
    "name": "Binaural Cuentas analiticas",
    "summary": """
       Modulo para las cuentas analiticas en la moneda alterna""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting",
    "version": "16.0.1.0.1",
    # any module necessary for this one to work correctly
    "depends": ["binaural_rate", "analytic", "binaural_accountant"],
    # always loaded
    "data": ["views/analytic_line_views.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
    "auto_install": True,
    "binaural":True,
}
