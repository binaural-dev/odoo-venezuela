# -*- coding: utf-8 -*-
{
    "name": "Binaural Cuentas anaíticas de Inventario",
    "summary": """
        Permite habilitar las cuentas analíticas en la valorización de inventario.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock/Analytic/Accounting",
    "version": "16.0.0.0.1",
    "depends": ["stock_account"],
    "data": [
        # 'security/ir.model.access.csv',
        "views/stock_picking_views.xml",
        "views/account_move_views.xml"
    ],
    "binaural": True,
}
