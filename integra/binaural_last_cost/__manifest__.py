{
    "name": "Binaural Último Costo",
    "summary": """
        Este modulo agrega el último costo al product y al product template. También permite
        utilizarlo como método para calcular el precio de venta en las tarifas.
    """,
    "author": "Binaural C.A.",
    "license": "LGPL-3",
    "website": "https://binauraldev.com",
    "category": "Technical",
    "version": "17.0.1.0.0",
    "depends": ["product", "purchase", "stock_account", "stock", "sale"],
    "data": [
        "security/res_groups.xml",
        "views/product_pricelist_views.xml",
        "views/product_views.xml",
        "views/purchase_views.xml",
        "views/product_product.xml",
        "views/account_move.xml",
    ],
    "binaural": True,
}
