{
    "name": "Binaural POS HR",
    "version": "16.0.1.0.2",
    "category": "Accounting",
    "summary": "Binaural POS HR",
    "sequence": "1",
    "license": "LGPL-3",
    "author": "Binaural.dev",
    "support": "contacto@binaural.dev",
    "depends": ["binaural_pos", "binaural_pos_discount", "pos_hr", "point_of_sale"],
    "data": [
        "views/res_config_settings.xml",
        "views/hr_employee.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_pos_hr/static/src/js/*.js",
            "binaural_pos_hr/static/src/xml/*.xml",
            "binaural_pos_hr/static/src/css/*.css",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": True,
    "binaural": True,
}
