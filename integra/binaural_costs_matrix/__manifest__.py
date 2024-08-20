{
    "name": "Binaural Matriz de Costos",
    "summary": """Modulo para la gestion de la matriz de costos""",
    "author": "Binauraldev",
    "license": "LGPL-3",
    "website": "https://www.binauraldev.com",
    "category": "Sales",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "product",
        "binaural_last_cost",
        "binaural_sale",
        "binaural_brand",
    ],
    # always loaded
    "data": [
        "views/product_pricelist_item_views.xml",
    ],
    "binaural": True,
}
