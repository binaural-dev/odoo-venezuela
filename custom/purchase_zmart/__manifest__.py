{
    "name": "Zmart Compras",
    "summary": """
       Modulo para compras personalizadas para smart""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Purchase/Purchase",
    "version": "16.0",
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
        "views/stock_picking.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
