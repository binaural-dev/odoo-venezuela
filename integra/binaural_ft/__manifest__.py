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
    "version": "16.0.1.0.5",
    "depends": [
        "point_of_sale",
        "binaural_pos_receipt",
    ],
    "data": [
        "report/invoice_mf_ticket.xml",
        "views/pos_payment_method.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "binaural_ft/static/src/js/*.js",
            "binaural_ft/static/src/xml/**/**.xml",
        ],
    },
    "binaural": True,
}
