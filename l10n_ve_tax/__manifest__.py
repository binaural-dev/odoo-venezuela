{
    "name": "Venezuela - Impuestos",
    "summary": """
        Impuestos para la localización en Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.0.0.13",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_ve_rate"],
    "data": [
        "views/res_config_settings.xml",
        "views/account_move.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "web.assets_backend": ["l10n_ve_tax/static/src/components/**/*"],
    },
}
