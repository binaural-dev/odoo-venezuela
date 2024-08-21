{
    "name": "Binaural Guía de Reparto",
    "summary": """Guia de reparto""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "17.0.1.0.0",
    "depends": ["stock", "sale_stock", "binaural_sale_stock", "binaural_seller_stock", "fleet"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/stock_picking_distribution_views.xml",
    ],
    "application": True,
}
