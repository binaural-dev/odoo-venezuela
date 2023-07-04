{
    "name": "Zmart Ventas",
    "summary": """
       Modulo para  personalizar campo en ventas para smart""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sale/Sale",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_sale",
    ],
    # always loaded
    "data": [
        # "security/ir.model.access.csv",
        "data/paperformat.xml",
        "data/mail_templates.xml",
        "data/ir_cron.xml",
        "report/report_sale.xml",
        "report/stock_report_view.xml",
        "report/report_deliveryslip.xml",
        "report/report_albaran.xml",
        "views/sale_order.xml",
        "views/stock_picking.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}