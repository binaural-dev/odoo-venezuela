{
    "name": "Binaural Marca Compras",
    "summary": """
        Maestro de marca en productos en Compras. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Inventory",
    "version": "16.0.0.2",
    "depends": ["stock", "purchase", "binaural_brand"],
    "data": [
        "views/purchase_order_views.xml",
        "reports/report_purchase.xml",
        "reports/report_purchase_order.xml",
    ],
    "auto_install": True,
    "application": True,
}
