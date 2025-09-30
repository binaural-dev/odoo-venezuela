{
    "name": "Cadipa Facturación",
    "summary": """
       Modulo para personalizaciones de facturacion de CADIPA """,
    "version": "17.0.1.0.5",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting",
    # any module necessary for this one to work correctly
    "depends": ["l10n_ve_invoice"],
    # always loaded
    "data": [
        # "report/sale_note_template.xml",
        "data/invoice_free_form_paperformat.xml",
        "report/report_invoice_free_form.xml",
        "report/report_invoice_free_form_bs.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
