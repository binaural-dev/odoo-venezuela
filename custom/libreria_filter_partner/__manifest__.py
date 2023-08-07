# -*- coding: utf-8 -*-
{
    "name": "Libreria filtro de contacto",
    "summary": """
        Cambiar el valor por defecto en el filtro de contacto a contacto en todos los modelos que
        lo tengan.
    """,
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Technical",
    "version": "16.1",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_filter_partner",
        "binaural_sale",
        "binaural_purchase",
        "binaural_invoice",
    ],
    # always loaded
    "data": [
        "views/sale_order.xml",
        "views/purchase_order.xml",
        "views/account_move.xml",
    ],
}
