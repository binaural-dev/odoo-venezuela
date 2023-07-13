{
    "name": "Seguridad Ventas",
    "summary": """
       Modulo para persolnalizar el formato de presupuesto""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sale/Sale",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": [
        "sale",
    ],
    # always loaded
    "data": [
        'security/ir.model.access.csv',
        'data/paperformat.xml',
        'reports/sale_report.xml',
        'views/sale_order.xml',
        'views/shipping_method.xml',
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
