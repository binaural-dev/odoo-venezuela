{
    "name": "Venezuela - Impuestos",
    "summary": """
        Impuestos para la localización en Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "18.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_ve_base", "l10n_ve_rate"],
    "data": [
        "views/res_config_settings.xml",
        "views/account_move.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    #FIXME: Se comenta el componente debido a refactorización de componente base
    # "assets": {
    #     "web.assets_backend": ["l10n_ve_tax/static/src/components/**/*"],
    # },
}
