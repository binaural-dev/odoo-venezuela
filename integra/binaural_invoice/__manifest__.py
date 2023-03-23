{
    "name": "Binaural Facturación",
    "summary": """
       Modulo para contabilidad Venezolana """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    # any module necessary for this one to work correctly
    "depends": ["binaural_accountant", "binaural_contact", "binaural_fiscal", "binaural_filter_partner"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "data/account_data.xml",
        "data/invoice_free_form_paperformat.xml",
        "data/invoice_sale_note_paperformat.xml",
        "report/report_invoice_free_form.xml",
        "report/report_invoice_sale_note.xml",
        "views/account_move.xml",
        "wizard/accounting_reports_views.xml",
    ],

    'images': ['static/description/icon.png'],

    'application': True
}
