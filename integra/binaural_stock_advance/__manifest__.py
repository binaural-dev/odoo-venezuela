{
    "name": "Binaural Importaciones",
    "summary": """
        Modulo de localización relacionado
        al inventario.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "stock",
        "binaural_rate",
        "binaural_last_cost",
        "purchase",
        "stock_landed_costs",
        "product",
        "stock_account",
        "binaural_tax",
        "binaural_filter_partner",
    ],
    "data": [
        "views/res_config_settings.xml",
        "views/stock_valuation_adjustment_lines.xml",
        "views/stock_landed_cost.xml",
        "views/product_product.xml",

    ],
    "binaural": True,
}
