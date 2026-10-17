{
    "name": "Deducibles - Contabilidad Binaural",
    "summary": """
        Descuentos globales deducibles (porcentaje o monto fijo) en facturas de proveedor y de cliente
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "19.0.1.0.0",
    "depends": [
        "l10n_ve_accountant",
        "l10n_ve_invoice",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
        "report/report_invoice_free_form.xml",
    ],
    "assets": {
        "web.assets_backend": ["l10n_ve_deductible/static/src/components/**/*"],
    },
    "auto_install": True,
    "images": ["static/description/icon.png"],
    "application": False,
    "installable": True,
}
