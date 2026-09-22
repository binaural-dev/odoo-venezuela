{
    "name": "Venezuela - The Factory HKA / Guía de Despacho",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "19.0.1.0.0",
    "depends": [
        "l10n_ve_invoice_digital",
        "l10n_ve_stock_account",
        "stock",
    ],
    "external_dependencies": {"python": ["requests", "pytz"]},
    "images": ["static/description/icon.png"],
    "application": True,
    "data": [
        "views/stock_picking.xml",
    ],
}
