{
    "name": "Venezuela - reglas para listas de precio",
    "version": "1.2",
    "license": "LGPL-3",
    "summary": "Módulo para gestionar reglas de listas de precio en Venezuela",
    "description": """
        Este módulo personaliza las reglas de listas de precio, precios en moneda extranjera y precios unitarios.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Purchase",
    "depends": ["account", "account_invoice_pricelist", "l10n_ve_sale"],
    "data": [
        "security/pricelist_security.xml",
        "views/account_invoice_view.xml",
        "views/sale_order.xml",
        "views/product_template_view.xml",
    ],
    "application": True,
    "images": ["static/description/icon.png"],
}

