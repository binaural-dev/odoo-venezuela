{
    "name": "Venezuela - Inventario/Compras",
    "version": "19.0.1.2.0",
    "license": "LGPL-3",
    "summary": "Módulo para gestionar inventario/compras en Venezuela",
    "description": """
        Este módulo personaliza el proceso de gestión de inventario/compras para cumplir con las regulaciones venezolanas.
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
