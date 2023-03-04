{
    'name': "Binaural Facturación",
    'summary': """
        Modulo para facturación Venezolana
    """,
    "license": "LGPL-3",
    'author': "Binauraldev",
    'website': "https://www.binauraldev.com/",
    'category': 'Invoicing / Management',
    'version': '16.0.0.0.1',
    'depends': ['account'],
    'data': [
        # 'security/ir.model.access.csv',
        "data/invoice_free_form_paperformat.xml",
        "data/invoice_sale_note_paperformat.xml",
        "report/report_invoice_free_form.xml",
        "report/report_invoice_sale_note.xml"
    ],
}
