{
    "name": "Binaural POS",
    "summary": """
       Modulo para Localizacion Venezolana en POS""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.2.16",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale", "binaural_rate", "binaural_contact", "binaural_stock"],
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
        "point_of_sale.assets": [
            "binaural_pos/static/src/js/*.js",
            "binaural_pos/static/src/xml/*.xml",
            "binaural_pos/static/src/css/*.css",
        ],
        "point_of_sale.qunit_suite_tests": [
            "binaural_pos/static/tests/unit/**/*",
        ],
    },
    "binaural": True,
}
