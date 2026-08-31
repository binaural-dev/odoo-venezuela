{
    "name": "Venezuela - Inventario/Compras",
    "version": "19.0.1.2.1",
    "license": "LGPL-3",
    "summary": "Inventario/compras VE: código alterno de producto en línea de compra",
    "description": """
        Este módulo personaliza el proceso de gestión de inventario/compras para cumplir con las regulaciones venezolanas.

        Incluye:
        * Búsqueda de producto por Código Alterno (name_search) en la línea de compra.
        * Columna "Código Alterno" (solo lectura) en la línea de la orden de compra.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Purchase",
    "depends": [
        "purchase_stock",
        "l10n_ve_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_views.xml",
    ],
    "application": True,
    "images": ["static/description/icon.png"],
}
