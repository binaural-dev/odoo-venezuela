{
    "name": "Binaural Tasa Inventario",
    "summary": """
        Modulo para calcular tasa en inventario
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock / Inventory",
    "version": "17.0.1.0.0",
    "depends": ["stock", "sale_stock", "purchase_stock", "binaural_sale", "binaural_purchase"],
    "data": [
        # 'security/ir.model.access.csv',
        "views/stock_picking.xml",
    ],
    "binaural": True,
}
