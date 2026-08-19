{
    "name": "Venezuela - POS Self Order / Kiosk",
    "summary": "Ajustes de l10n_ve_pos para el Kiosko/Autopedido nativo: moneda foránea e identificación del cliente por cédula",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Point of Sale",
    "version": "1.1",
    "depends": [
        "l10n_ve_pos",
        "pos_self_order",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "l10n_ve_pos_self_order/static/src/**/*",
        ],
    },
    "auto_install": True,
    "application": True,
    "binaural": True,
}
