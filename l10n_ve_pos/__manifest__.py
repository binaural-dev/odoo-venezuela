{
    "name": "Venezuela - POS",
    "summary": """
       Localización Venezolana en POS""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.1.0.10",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "point_of_sale",
        "pos_sale",
        "l10n_ve_location",
        "l10n_ve_rate",
        "l10n_ve_contact",
        "l10n_ve_stock",
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
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            "l10n_ve_pos/static/src/js/*.js",
            "l10n_ve_pos/static/src/xml/*.xml",
            "l10n_ve_pos/static/src/css/*.css",
        ],
    },
    "l10n_ve": True,
}
