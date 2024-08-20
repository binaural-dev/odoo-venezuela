{
    "name": "Binaural POS Cierre de Caja",
    "summary": """
       Modulo para Localizacion Venezolana en POS y Cierre de Caja""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale", "binaural_pos", "binaural_accountant"],
    # always loaded
    "data": [
        "views/pos_session_views.xml",
        "views/pos_config_views.xml",
        "views/pos_bill_views.xml",
    ],
    # "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": ["binaural_pos_close/static/src/**/*"],
    },
    "binaural": True,
}
