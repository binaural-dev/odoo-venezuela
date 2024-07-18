{
    "name": "Binaural Marca en POS",
    "summary": """
        Marca en el informe del POS y en la linea de pedidos del punto de venta.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Point of Sale",
    "version": "16.0.1.0.1",
    "depends": ["point_of_sale", "binaural_brand"],
    "data": [
        "views/pos_order_views.xml",
        "views/sale_report_view.xml",
    ],
    "application": True,
    "auto_install": True,
    "binaural":True,
}
