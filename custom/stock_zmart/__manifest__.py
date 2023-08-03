{
    "name": "Zmart Stock",
    "summary": """
       Modulo para  personalizar campo en modulo de inventario""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Stock",
    "version": "16.0",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_sale",
    ],
    # always loaded
    "data": [
        # "security/ir.model.access.csv",
        "data/paperformat.xml",
        # "data/mail_templates.xml",
        # "data/ir_cron.xml",
        "report/picking_order_report.xml",
        "report/report_albaran.xml",
        # "report/report_deliveryslip.xml",
        # "report/report_albaran.xml",
        # "views/sale_order.xml",
        "views/stock_picking.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}