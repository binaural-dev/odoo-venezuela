{
    "name": "Venezuela - POS con IGTF",
    "summary": "Módulo para calcular el IGTF (Impuesto sobre transacciones financieras grandes) en POS.",
    "license": "LGPL-3",
    "description": "Modulo para calculos del impuesto IGTF (Impuesto a las grandes transacciones financieras) en POS",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.0.0.0",
    "depends": [
        "base",
        "l10n_ve_pos",
        "l10n_ve_pos_igtf",
    ],
    "data": [
        "views/pos_payment_method.xml",
        "views/pos_payment_views.xml",
        "views/pos_order.xml",
        "views/pos_config.xml",
        "views/res_config_settings.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_pos_igtf/static/src/**/*",
        ],
    },
    "application": True,
    "binaural": True,
}
