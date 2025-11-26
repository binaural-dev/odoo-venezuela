{
    "name": "Venezuela - reglas para listas de precio",
    "version": "1.0",
    "license": "LGPL-3",
    "summary": "Módulo para gestionar reglas de listas de precio en Venezuela",
    "description": """
        Este módulo personaliza las reglas de listas de precio.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Purchase",
    "depends": ["account","sale", "account_invoice_pricelist"],
    "data": [
        "security/pricelist_security.xml",
        "views/account_invoice_view.xml",
    ],
    "application": True,
    "images": ["static/description/icon.png"],
}

