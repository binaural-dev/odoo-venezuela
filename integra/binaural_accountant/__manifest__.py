{
    "name": "Binaural Contabilidad",
    "summary": """
       Modulo para contabilidad Venezolana """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "16.4.12",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "web",
        "account_accountant",
        "account_sequence",
        "binaural_tax",
        "binaural_contact",
        "binaural_rate",
        "binaural_fiscal",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "data/account_data.xml",
        "data/ir_actions_server.xml",
        "views/account_invoice_report.xml",
        "views/account_move.xml",
        "views/account_move_line.xml",
        "views/account_payment.xml",
        "views/res_partner.xml",
        "report/account_invoice_details.xml",
        "report/all_payment_report.xml",
        "wizard/account_payment_register.xml",
        "wizard/invoices_details.xml",
        "wizard/payment_report.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
