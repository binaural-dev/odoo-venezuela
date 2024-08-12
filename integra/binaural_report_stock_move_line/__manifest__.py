{
    "name": "Binaural Reporte de movimientos en stock",
    "summary": """
        Modulo de reporte de movimientos en stock.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock/Report",
    "version": "17.0.1.0.0",
    "depends": [
        "binaural_stock",        
        "purchase",
        "sale",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "report/stock_move_line_report_views.xml",
        "views/stock_move_line.xml",
    ],
    "binaural": True,
}
