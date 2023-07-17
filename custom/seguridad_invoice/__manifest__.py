{
    "name": "Seguridad Invoice",
    "summary": """
       Modulo para personalizar formato de factura en seguridad""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Account/Account",
    "version": "16.0",
    "depends": [
        "account",
    ],
    "data": [
        'data/paperformat.xml',
        'reports/account_report.xml',
        # 'reports/account_report_ven.xml',
       
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
