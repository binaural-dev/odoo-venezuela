# -*- coding: utf-8 -*-
{
    "name": "Binaural FT",
    "summary": """
        Modulo para modificar formatos de reportes.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0.1.0.0",
    "depends": [
        "stock",
        "binaural_stock",
        "point_of_sale",
        "binaural_pos_receipt",
        "binaural_invoice",
        "binaural_payment_extension",
    ],
    "data": [
        "report/dispatch_note.xml",
        "report/delivery_note.xml",
        "report/sale_order_ticket.xml",
        "report/invoice_mf_ticket.xml",
        "report/freeform.xml",
        "report/freeform_header.xml",
        "views/stock_picking.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_ft/static/src/js/*.js",
            "binaural_ft/static/src/xml/**/**.xml",
            # "binaural_ft/static/src/css/*.css",
        ],
    },
}
