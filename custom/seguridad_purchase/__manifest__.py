{
    "name": "Seguridad Compras",
    "summary": """
       Modulo para personalizar el formato de presupuesto y pedidos en el modulo de compras""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Purchase/Purchase",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": [
        "purchase",
    ],
    # always loaded
    "data": [
        'data/paperformat.xml',
        'reports/purchase_report.xml',
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}