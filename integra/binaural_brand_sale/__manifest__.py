{
    "name": "Binaural Marca Ventas",
    "summary": """
        Maestro de marca en productos en Ventas. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Inventory",
    "version": "17.0.1.0.0",
    "depends": ["stock", "sale", "binaural_brand"],
    "data": [
        "views/sale_order_views.xml",
        "views/sale_report_view.xml",
        "views/product_pricelist_item_views.xml",
        "reports/report_sale.xml",
    ],
    "auto_install": True,
    "application": True,
}
