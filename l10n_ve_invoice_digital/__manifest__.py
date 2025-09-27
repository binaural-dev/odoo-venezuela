{
    "name": "Venezuela - Facturación Digital",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.0.0.10",
    "depends": [
        "account",
        "l10n_ve_igtf",
        "account_debit_note",
        "l10n_ve_invoice",
        "l10n_ve_payment_extension",
    ],

    "images": ["static/description/icon.png"],
    "application": True,
    "data": [
        "data/payment_method_data_tfhka.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/account_move_view.xml",
        "views/account_retention_iva.xml",
        "views/account_retention_islr.xml",
        "wizard/account_retention_alert_views.xml",
        "views/account_journal.xml",
        "views/payment_method_tfhka.xml",
    ],
}
