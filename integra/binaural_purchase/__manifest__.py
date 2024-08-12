{
    "name": "Binaural Compras",
    "summary": """
       Modulo para compras """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Purchase/Purchase",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "purchase",
        "binaural_tax",
        "binaural_rate",
        "binaural_filter_partner",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order.xml",
        "views/res_config_settings.xml",
        "views/res_partner.xml",
        "views/product_template.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
}
