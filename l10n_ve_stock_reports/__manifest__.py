{
    "name": "Venezuela - Libro de Inventario",
    "summary": """
        Módulo de libro de Inventario Venezuela
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock / Inventory",
    "version": "18.0.0.0.8",
    "depends": ["stock", "account","sale_stock"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/stock_book_report.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
}
