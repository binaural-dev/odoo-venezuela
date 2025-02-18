{
    "name": "Binaural Impuesto",
    "summary": """
       Modulo para Impuestos Venezolanos""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.1.0.2",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_ve_rate"],
    # always loaded
    "data": [
        "views/res_config_settings.xml",
        "views/account_move.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "web.assets_backend": ["l10n_ve_tax/static/src/components/**/*"],
    },
    "binaural": True,
}
