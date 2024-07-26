{
    "name": "Binaural Vendedores",
    "summary": """
         Modulo para vendedores """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "version": "16.0.1.0.3",
    "category": "Hr/Invoicing/Account",
    "depends": [
        "account",
        "contacts",
        "hr",
        "binaural_rate",
        "binaural_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/res_partner.xml",
        "data/res_users.xml",
        "data/hr_employee.xml",
        "report/account_invoice_report.xml",
        "report/sale_report.xml",
        "views/account_move.xml",
        "views/res_partner.xml",
        "views/res_config_settings.xml",
        "views/hr_employee.xml",
        "views/sale_order.xml",
    ],
    "images": ["static/description/icon.png"],
    "binaural": True,
}

