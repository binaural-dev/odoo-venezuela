{
    "name": "Binaural Margen",
    "summary": """
        Margen de ventas
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sale",
    "version": "17.0.1.0.0",
    "depends": ["sale_margin","binaural_last_cost","sale","purchase", "binaural_base"],
    "data": [
        "data/res_groups.xml",
        "views/sale_order.xml",
        "views/purchase_order.xml",
        "views/account_move.xml",
    ],
    "application": True,
    "binaural": True,
}
