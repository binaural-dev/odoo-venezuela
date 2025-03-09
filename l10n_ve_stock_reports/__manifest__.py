{
    "name": "Binaural Libro de Inventario",
    "summary": """
        Modulo de libro de Inventario
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock / Inventory",
    "version": "16.0.0.0.3",
    "depends": ["stock", "account","sale_stock","l10n_ve_invoice"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/stock_book_report.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
}
