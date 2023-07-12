{
    "name": "Seguridad Stock",
    "summary": """
       Modulo para personalizar formato de etiqueta en comanda""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Stock",
    "version": "16.0",
    "depends": [
        "stock","seguridad_sale",
    ],
    "data": [
        'data/paperformat.xml',
        'reports/report_etiqueta.xml',
        'views/stock_picking.xml',
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
