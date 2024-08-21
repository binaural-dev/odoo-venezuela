{
    "name": "Binaural Scale PLU",
    "summary": """
       Modulo para descargar archivo plu""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "version": "17.0.1.0.0",
    "depends": [
        "product",
        "stock",
        "binaural_rate",
        "point_of_sale",
        "binaural_pos",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template.xml",
        "views/res_config_settings_views.xml",
        "wizards/plu_product.xml",
    ],
    "assets": {
        "point_of_sale.assets": ["binaural_scale/static/src/js/*.js"],
    },
    "application": True,
    "binaural": True,
}
