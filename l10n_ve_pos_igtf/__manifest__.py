{
    "name": "Venezuela - POS with IGTF",
    "summary": "Module for calculating the IGTF (Tax on Large Financial Transactions) in POS.",
    "license": "LGPL-3",
    "description": "Module for calculating the IGTF (Tax on Large Financial Transactions) in POS.",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "16.0.1.0.2",
    "depends": ["base", "l10n_ve_pos", "l10n_ve_igtf", "l10n_ve_sale"],
    "data": [
        "views/pos_payment_method.xml",
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
