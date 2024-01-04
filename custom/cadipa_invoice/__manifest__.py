{
    "name": "Cadipa Facturación",
    "summary": """
       Modulo para personalizaciones de facturacion de CADIPA """,
    "version": "16.0.1.0.0",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting",
    # any module necessary for this one to work correctly
    "depends": ["binaural_invoice"],
    # always loaded
    "data": ["report/sale_note_template.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
}
