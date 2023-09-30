{
    "name": "Zmart Ventas",
    "summary": """
       Modulo para  personalizar campo en ventas para zmart""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sale/Sale",
    "version": "16.0.0.5",
    "depends": [
        "sale","invoice_zmart"
    ],
    "data": [
        'data/res_group.xml',
        "data/paperformat.xml",
        "data/mail_templates.xml",
        "data/ir_cron.xml",
        "report/delivery_note_rma.xml",
        "report/report_sale.xml",
        "report/stock_report_view.xml",
        'report/sale_order_note_usd.xml',
        "views/sale_order.xml",
        "views/stock_picking.xml",
        "views/res_company.xml"
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}