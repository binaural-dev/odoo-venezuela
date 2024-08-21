{
    "name": "Binaural Catalogo de Producto en Ventas",
    "version": "17.0.1.0.0",
    "category": "stock",
    "summary": """
        Este módulo se utiliza para agregar productos como la funcionalidad de agregar carrito
        """,
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "depends": ["sale", "product", "sale_management", "binaural_stock"],
    "data": [
        "views/sale_order.xml",
        "views/product_product_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["binaural_sale_product_catalog/static/src/components/**/*"],
    },
    "images": ["static/description/icon.png"],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    "binaural": True,
}
