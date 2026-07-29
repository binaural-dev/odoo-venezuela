{
    "name": "Venezuela - Facturación con Máquina Fiscal (Web Serial)",
    "summary": "Impresión de facturas, notas de crédito y notas de débito en "
    "impresoras fiscales The Factory HKA vía Web Serial API desde "
    "Contabilidad/Facturación.",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "license": "LGPL-3",
    "author": "Binaural",
    "support": "contacto@binaural.dev",
    "depends": [
        "account",
        "web",
        "l10n_ve_mf_base",
        "l10n_ve_invoice",
        "l10n_ve_accountant",
        "l10n_ve_stock_account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move.xml",
        "views/account_move_views.xml",
        "views/account_journal.xml",
        "views/res_config_settings.xml",
        "wizards/mf_reports_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_account_mf/static/src/backend/*.js",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "binaural": True,
}
