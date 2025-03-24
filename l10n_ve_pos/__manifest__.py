{
    "name": "Venezuela - POS (Punto de Venta)",
    "summary": """
        Módulo de POS (Punto de Venta) en Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "support": "contacto@binaural.dev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "17.0.0.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "point_of_sale",
        "l10n_ve_rate",
        "l10n_ve_contact",
        "l10n_ve_stock",
        "l10n_ve_location",
        "l10n_ve_accountant",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "data/res_group.xml",
        "views/pos_payment_method.xml",
        "views/pos_order.xml",
        "views/res_config_settings.xml",
        "views/pos_config_views.xml",
        "views/pos_payment_views.xml",
        "views/report_saledetails.xml",
        "security/res_group.xml",
        "wizard/payment_report.xml",
        "report/payment_report.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale._assets_pos": [
            "l10_ve_pos/static/src/**/**",
            "l10_ve_pos/static/src/**/**/**/*",
        ],
    },
}
