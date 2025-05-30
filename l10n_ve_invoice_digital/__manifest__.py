{
    "name": "Venezuela - Facturación Digital",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.0.0.15",
    "depends": [
        "base",
        "account",
        "account_debit_note",
        "l10n_ve_invoice",
        "l10n_ve_iot_mf",
        "l10n_ve_stock_account",
        "stock",
    ],
    
    "images": ["static/description/icon.png"],
    "application": True,
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/account_move_view.xml",
        "views/account_retention_iva.xml",
        "views/account_retention_islr.xml",
        "views/stock_picking.xml",
        "wizard/account_retention_alert_views.xml",
    ],
}