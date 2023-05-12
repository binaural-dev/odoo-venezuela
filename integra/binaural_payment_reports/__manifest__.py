{
    "name": "Binaural Reporte de anticipos",
    "summary": """
       Modulo para Reporte de anticipos """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Igtf",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "account_accountant"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "wizard/advance_payment_report.xml",
        "report/report_advance_payment.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
