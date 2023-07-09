{
    "name": "Zmart Ventas",
    "summary": """
       Modulo para  personalizar campo en ventas para zmart""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sale/Sale",
    "version": "16.1",
    "depends": [
        "binaural_sale",
    ],
    "data": [
        "data/paperformat.xml",
        "data/mail_templates.xml",
        "data/ir_cron.xml",
        "report/report_sale.xml",
        "report/stock_report_view.xml",
        "views/sale_order.xml",
        "views/stock_picking.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}