{
    "name": "Binaural Anticipos IGTF",
    "summary": """
       Modulo para Anticipos en contabilidad Venezolana """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Igtf",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "binaural_accountant",
        "binaural_tax",
        "binaural_rate",
        "binaural_fiscal",
        "binaural_igtf",
        "binaural_advance_payment",
    ],
    # always loaded
    "data": [
        "views/res_config_settings.xml",
    ],
    "images": ["static/description/icon.png"],
    "auto_install": True,
}
