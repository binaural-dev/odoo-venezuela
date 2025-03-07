{
    "name": "Venezuela - POS with IGTF",
    "summary": "Módulo para calculos del impuesto IGTF (Impuesto a las grandes transacciones financieras) en POS",
    "license": "AGPL-3",
    "description": "Módulo para calculos del impuesto IGTF (Impuesto a las grandes transacciones financieras) en POS",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "16.0.1.0.1",
    "depends": ["base", "l10n_ve_pos", "l10n_ve_igtf", "l10n_ve_sale"],
    "data": [
        "views/pos_payment_method.xml",
        "views/pos_config.xml",
        "views/res_config_settings.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "point_of_sale.assets": [
            "l10n_ve_pos_igtf/static/src/js/*.js",
            "l10n_ve_pos_igtf/static/src/xml/*.xml",
            "l10n_ve_pos_igtf/static/src/css/*.css",
        ],
    },
    "application": True,
}
