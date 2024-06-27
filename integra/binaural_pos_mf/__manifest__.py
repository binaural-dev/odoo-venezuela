{
    "name": "Binaural POS with IoT MF",
    "version": "16.0.1.1.3",
    "category": "Accounting",
    "summary": "Binaural POS with IoT MF",
    "description": "Binaural POS with IoT MF",
    "sequence": "1",
    "license": "LGPL-3",
    "author": "Binaural.dev",
    "support": "contacto@binaural.dev",
    "depends": ["point_of_sale", "binaural_pos", "pos_iot", "binaural_iot_mf"],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_config.xml",
        "views/pos_order.xml",
        "views/pos_session.xml",
        "views/account_move.xml",
        "views/pos_payment_method.xml",
        "wizard/wizard_sales_book.xml",
        "views/res_config_settings.xml"
    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_mf/static/src/js/*.js",
            "binaural_pos_mf/static/src/xml/*.xml",
            "binaural_pos_mf/static/src/css/*.css",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "binaural": True,
}
