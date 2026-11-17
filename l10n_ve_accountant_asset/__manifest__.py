{
    "name": "Venezuela - Contabilidad - Activos Fijos",
    "summary": """
        Publicación automática personalizada (auto_post = custom: espera en borrador y la
        publica el cron en la fecha indicada) y puente con los activos fijos: las cuotas
        de depreciación futuras esperan en borrador y las publica el cron en su fecha.
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "19.0.1.0.1",
    "depends": ["l10n_ve_accountant", "account_asset"],
    "data": ["views/account_move_views.xml", "views/account_asset_views.xml"],
    "installable": True,
    "application": False,
    "auto_install": True,
}
